from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.schema.orders import OrderRequest, OrderStatus
from app.schema.payments import (
    PaymentMethod,
    PaymentStatus,
    PaymentGateway,
    GatewayWebhookEvent,
)
from app.models.orders import Orders, OrderItems, PaymentDetails
from app.models.cart import ProductCart
from app.models.user import Users
from app.models.product import Products
from app.exception.order_exception import InvalidOrderError, ProductOutOfStock
from app.exception.product_exception import InvalidProductError
from app.exception.payment_exception import PaymentGatewayError
from app.exception.cart_exception import CartEmptyError
from app.services.auth import SUPER_ROLES
from app.services.product import get_product_by_id, restock_product
from app.services.payments import PaymentGatewayAdapter, PaymentGatewayFactory
from app.services.cart import get_all_cart_items_for_user
from decimal import Decimal
from typing import cast


async def search_order_by_id(db: AsyncSession, id: int, user: Users) -> Orders:
    loader = (selectinload(Orders.order_items), selectinload(Orders.payment_detail))
    if cast(str, user.role) in SUPER_ROLES:
        result = await db.execute(
            select(Orders).options(*loader).where(Orders.id == id)
        )
    else:
        result = await db.execute(
            select(Orders)
            .options(*loader)
            .where(Orders.user_id == cast(int, user.id), Orders.id == id)
        )
    result = result.scalar_one_or_none()
    if not result:
        raise InvalidOrderError()
    return result


async def search_order_items_by_order_id(
    db: AsyncSession, id: int, user: Users
) -> list[OrderItems]:
    order: Orders = await search_order_by_id(db, id, user)
    return list(order.order_items)


async def search_payment_details_by_order(
    db: AsyncSession, order: Orders
) -> PaymentDetails:
    return order.payment_detail


async def list_all_orders(db: AsyncSession, user: Users) -> list[Orders]:
    if cast(str, user.role) in SUPER_ROLES:
        result = await db.execute(select(Orders).order_by(Orders.created_at.desc()))
    else:
        result = await db.execute(
            select(Orders)
            .where(Orders.user_id == cast(int, user.id))
            .order_by(Orders.created_at.desc())
        )
    result = result.scalars().all()
    return cast(list, result)


async def buy_product_through_id(
    db: AsyncSession,
    product_id: int,
    tax: Decimal,
    user: Users,
    payload: OrderRequest,
):
    product: Products | None = await get_product_by_id(db, product_id)
    if not product:
        raise InvalidProductError()
    net_price: Decimal = cast(Decimal, product.price) - cast(Decimal, product.discount)
    grand_total = net_price + round((net_price * tax / 100), 2)
    orderdetail = Orders(
        user_id=user.id,
        subtotal=product.price,
        discount=product.discount,
        tax=tax,
        grand_total=grand_total,
        customer_name=payload.customer.name,
        customer_mobile=payload.customer.mobile,
        customer_email=payload.customer.email,
    )

    try:
        inventory_update = await db.execute(
            update(Products)
            .where(
                Products.id == product_id,
                Products.inventory > 0,
                Products.is_deleted.is_(False),
            )
            .values(inventory=Products.inventory - 1)
            .returning(Products.id)
        )
        if inventory_update.scalar_one_or_none() is None:
            raise ProductOutOfStock()
        db.add(orderdetail)
        # Gettng order_id without commit
        await db.flush()
        # Creating orderitem entry
        orderitem = OrderItems(
            order_id=orderdetail.id,
            product_id=product.id,
            product_name=product.name,
            unit_price=product.price,
            discount=product.discount,
            net_price=net_price,
            tax=tax,
            total_price=grand_total,
        )
        db.add(orderitem)
        # Creating a payment entry
        paymentdetail = PaymentDetails(
            order_id=orderdetail.id,
            gateway=(
                PaymentGateway.CASH
                if payload.method == PaymentMethod.CASH
                else payload.gateway
            ),
            method=payload.method,
            amount=grand_total,
        )
        db.add(paymentdetail)
        if payload.method == PaymentMethod.CASH:
            setattr(paymentdetail, "status", PaymentStatus.SUCCESSFUL)
            setattr(orderdetail, "order_status", OrderStatus.SUCCESSFUL)
        await db.commit()
        await db.refresh(orderdetail)
        await db.refresh(product)
        await db.refresh(paymentdetail)
    except Exception:
        await db.rollback()
        raise
    if payload.method == PaymentMethod.CASH:
        await db.refresh(orderdetail, attribute_names=["payment_detail"])
        return orderdetail, None

    try:
        adapter: PaymentGatewayAdapter = PaymentGatewayFactory.get(payload.gateway)
        result = adapter.create_payment(orderdetail, paymentdetail)
        setattr(paymentdetail, "transaction_reference", result.transaction_reference)
        await db.commit()
        await db.refresh(paymentdetail)
    except Exception as e:
        await db.rollback()
        await restock_product(db, product_id, 1)
        setattr(orderdetail, "order_status", OrderStatus.FAILED)
        setattr(paymentdetail, "status", PaymentStatus.FAILED)
        await db.commit()
        await db.refresh(orderdetail)
        await db.refresh(paymentdetail)
        raise PaymentGatewayError("gateway create_payment failed") from e

    gateway_client: dict | None = None
    if result.client_secret:
        gateway_client = {"client_secret": result.client_secret}
    elif result.checkout_url:
        gateway_client = {"checkout_url": result.checkout_url}
    await db.refresh(orderdetail, attribute_names=["payment_detail"])
    return orderdetail, gateway_client


async def checkout_cart_for_user(
    db: AsyncSession, user: Users, tax: Decimal, payload: OrderRequest
):
    try:
        cart_items = await get_all_cart_items_for_user(db, cast(int, user.id))
        if not cart_items:
            raise CartEmptyError()
        sub_total = 0
        total_discount = 0
        net_total = 0
        grand_total = 0
        total_quantity = 0
        restock_lines: list[tuple[int, int]] = []
        for entry in cart_items:
            product = await get_product_by_id(db, cast(int, entry.product_id))
            # Stale cart row (product deleted) — fail checkout, cart stays intact
            if not product:
                raise InvalidProductError()
            sub_total = sub_total + (product.price * entry.quantity)
            total_discount = total_discount + (product.discount * entry.quantity)
            net_total = sub_total - total_discount
            total_quantity += entry.quantity
            restock_lines.append(
                (cast(int, entry.product_id), cast(int, entry.quantity))
            )
        grand_total = net_total + round(((cast(Decimal, net_total) * tax) / 100), 2)
        orderdetail = Orders(
            user_id=user.id,
            total_items=total_quantity,
            subtotal=sub_total,
            discount=total_discount,
            tax=tax,
            grand_total=grand_total,
            customer_name=payload.customer.name,
            customer_mobile=payload.customer.mobile,
            customer_email=payload.customer.email,
        )
        db.add(orderdetail)
        await db.flush()
        for entry in cart_items:
            product = await get_product_by_id(db, cast(int, entry.product_id))
            if product:
                unit_net: Decimal = cast(Decimal, product.price) - cast(
                    Decimal, product.discount
                )
                line_net = unit_net * cast(int, entry.quantity)
                line_total = line_net + round((line_net * tax / 100), 2)
                orderitem = OrderItems(
                    order_id=orderdetail.id,
                    product_id=entry.product_id,
                    product_name=product.name,
                    quantity=entry.quantity,
                    unit_price=product.price,
                    discount=product.discount,
                    net_price=unit_net,
                    tax=tax,
                    total_price=line_total,
                )
                db.add(orderitem)
        # Creating a payment entry
        paymentdetail = PaymentDetails(
            order_id=orderdetail.id,
            gateway=(
                PaymentGateway.CASH
                if payload.method == PaymentMethod.CASH
                else payload.gateway
            ),
            method=payload.method,
            amount=orderdetail.grand_total,
        )
        db.add(paymentdetail)
        if payload.method == PaymentMethod.CASH:
            setattr(paymentdetail, "status", PaymentStatus.SUCCESSFUL)
            setattr(orderdetail, "order_status", OrderStatus.SUCCESSFUL)
        # Delete cart rows in the SAME transaction as the order (no inventory change)
        await db.execute(
            delete(ProductCart).where(ProductCart.user_id == cast(int, user.id))
        )
        await db.commit()
        await db.refresh(orderdetail)
        await db.refresh(paymentdetail)
    except Exception:
        await db.rollback()
        raise
    if payload.method == PaymentMethod.CASH:
        await db.refresh(orderdetail, attribute_names=["payment_detail"])
        return orderdetail, None
    try:
        adapter: PaymentGatewayAdapter = PaymentGatewayFactory.get(payload.gateway)
        result = adapter.create_payment(orderdetail, paymentdetail)
        setattr(paymentdetail, "transaction_reference", result.transaction_reference)
        await db.commit()
        await db.refresh(paymentdetail)
    except Exception as e:
        await db.rollback()
        for product_id, quantity in restock_lines:
            await restock_product(db, product_id, quantity)
        setattr(orderdetail, "order_status", OrderStatus.FAILED)
        setattr(paymentdetail, "status", PaymentStatus.FAILED)
        await db.commit()
        await db.refresh(orderdetail)
        await db.refresh(paymentdetail)
        raise PaymentGatewayError("gateway create_payment failed") from e

    gateway_client: dict | None = None
    if result.client_secret:
        gateway_client = {"client_secret": result.client_secret}
    elif result.checkout_url:
        gateway_client = {"checkout_url": result.checkout_url}
    await db.refresh(orderdetail, attribute_names=["payment_detail"])
    return orderdetail, gateway_client


async def get_payment_by_reference(
    db: AsyncSession, transaction_reference: str
) -> PaymentDetails | None:
    result = await db.execute(
        select(PaymentDetails).where(
            PaymentDetails.transaction_reference == transaction_reference
        )
    )
    return result.scalar_one_or_none()


async def restock_order_lines(db: AsyncSession, order: Orders) -> None:
    result = await db.execute(select(OrderItems).where(OrderItems.order_id == order.id))
    for item in result.scalars().all():
        await restock_product(db, cast(int, item.product_id), cast(int, item.quantity))


async def apply_webhook_event(db: AsyncSession, event: GatewayWebhookEvent) -> None:
    payment = await get_payment_by_reference(db, event.transaction_reference)
    if payment is None:
        return  # unknown payment — not ours, acknowledge and ignore
    if cast(PaymentStatus, payment.status) != PaymentStatus.PENDING:
        return  # idempotent: already terminal (SUCCESSFUL or FAILED), do nothing
    order = await db.get(Orders, payment.order_id)
    if order is None:
        return  # orphan payment row without an order, ignore
    if event.success:
        setattr(payment, "status", PaymentStatus.SUCCESSFUL)
        setattr(order, "order_status", OrderStatus.SUCCESSFUL)
    else:
        setattr(payment, "status", PaymentStatus.FAILED)
        setattr(order, "order_status", OrderStatus.FAILED)
        await restock_order_lines(db, order)
    await db.commit()
