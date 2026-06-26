"""
Seed script: creates superadmin user and populates default settings.
Run once after first migration:
    docker exec marketplace_backend python scripts/seed.py
"""
import asyncio
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.models import User, UserRole, Category
from app.services.settings_service import get_all_settings
from app.services.referral_service import ensure_referral_code


async def seed():
    async with AsyncSessionLocal() as db:
        # Create superadmin
        result = await db.execute(
            select(User).where(User.email == settings.FIRST_SUPERUSER_EMAIL)
        )
        if not result.scalar_one_or_none():
            admin = User(
                email=settings.FIRST_SUPERUSER_EMAIL,
                password_hash=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                full_name=settings.FIRST_SUPERUSER_NAME,
                role=UserRole.superadmin,
                is_superuser=True,
                is_staff=True,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            await ensure_referral_code(admin, db)
            print(f"✓ Superadmin created: {settings.FIRST_SUPERUSER_EMAIL}")
        else:
            print(f"  Superadmin already exists: {settings.FIRST_SUPERUSER_EMAIL}")

        # Populate default settings
        await get_all_settings(db)
        print("✓ Default settings populated")

        # Create default categories
        default_categories = [
            {"name": "Одежда и обувь", "slug": "clothing", "sort_order": 1},
            {"name": "Электроника", "slug": "electronics", "sort_order": 2},
            {"name": "Дом и сад", "slug": "home-garden", "sort_order": 3},
            {"name": "Красота и здоровье", "slug": "beauty-health", "sort_order": 4},
            {"name": "Спорт и отдых", "slug": "sport", "sort_order": 5},
            {"name": "Игрушки и детские товары", "slug": "toys", "sort_order": 6},
            {"name": "Книги и хобби", "slug": "books-hobby", "sort_order": 7},
            {"name": "Handmade", "slug": "handmade", "sort_order": 8},
        ]
        for cat_data in default_categories:
            existing = await db.execute(
                select(Category).where(Category.slug == cat_data["slug"])
            )
            if not existing.scalar_one_or_none():
                cat = Category(**cat_data)
                db.add(cat)

        await db.commit()
        print("✓ Default categories created")

        # Default seller tariff plans (the classic free-high-commission vs
        # paid-low-commission trade-off). Admin can edit these in the panel.
        from app.models.models import SellerPlan
        default_plans = [
            {
                "name": "Бесплатный", "description": "Размещение без абонентской платы, но с повышенной комиссией платформы.",
                "monthly_price": 0, "commission_percent": 15, "trial_days": 0,
                "is_active": True, "is_default": True, "sort_order": 1,
            },
            {
                "name": "Старт", "description": "Сниженная комиссия за небольшую месячную плату. Первый месяц бесплатно.",
                "monthly_price": 990, "commission_percent": 8, "trial_days": 30,
                "is_active": True, "is_default": False, "sort_order": 2,
            },
            {
                "name": "Профи", "description": "Минимальная комиссия для активных продавцов.",
                "monthly_price": 2990, "commission_percent": 5, "trial_days": 14,
                "is_active": True, "is_default": False, "sort_order": 3,
            },
        ]
        for plan_data in default_plans:
            existing = await db.execute(select(SellerPlan).where(SellerPlan.name == plan_data["name"]))
            if not existing.scalar_one_or_none():
                db.add(SellerPlan(**plan_data))
        await db.commit()
        print("✓ Default seller plans created")

        # Default filterable attributes
        from app.models.models import Attribute
        default_attrs = [
            {"name": "Бренд", "slug": "brand", "is_filterable": True, "sort_order": 1},
            {"name": "Материал", "slug": "material", "is_filterable": True, "sort_order": 2},
            {"name": "Цвет", "slug": "color", "is_filterable": True, "sort_order": 3},
            {"name": "Страна производства", "slug": "country", "is_filterable": True, "sort_order": 4},
        ]
        for attr_data in default_attrs:
            existing = await db.execute(select(Attribute).where(Attribute.slug == attr_data["slug"]))
            if not existing.scalar_one_or_none():
                db.add(Attribute(**attr_data))
        await db.commit()
        print("✓ Default attributes created")

        # Default currency rates (base = RUB)
        from app.models.models import CurrencyRate, CurrencyCode
        default_currencies = [
            {"code": CurrencyCode.RUB, "rate": 1, "symbol": "₽"},
            {"code": CurrencyCode.USD, "rate": Decimal("0.011"), "symbol": "$"},
            {"code": CurrencyCode.EUR, "rate": Decimal("0.010"), "symbol": "€"},
        ]
        for cur in default_currencies:
            existing = await db.execute(select(CurrencyRate).where(CurrencyRate.code == cur["code"]))
            if not existing.scalar_one_or_none():
                db.add(CurrencyRate(**cur))
        await db.commit()
        print("✓ Default currency rates created")

        print("\n✅ Reference seed complete!")
        print(f"   Admin: {settings.FIRST_SUPERUSER_EMAIL} / {settings.FIRST_SUPERUSER_PASSWORD}")

    # Demo data (one coherent row per remaining table) so the DB isn't empty.
    await seed_demo()


async def seed_demo():
    """
    Create one coherent demo record per remaining table so a fresh database has
    something to show. Idempotent: keyed on the demo seller's email — if it
    already exists, this is skipped entirely.

    Scenario: a seller with a shop sells two products; a buyer purchases both in
    one completed order (paid, fiscalized, delivered), leaves a verified review
    the seller replies to, opens a return, chats with the shop, etc.
    """
    import json
    from datetime import datetime, timezone, timedelta
    from app.models.models import (
        Shop, ShopStatus, SellerRequisites, TaxRegime, SellerSubscription, SubscriptionStatus,
        SellerPlan, Category, Product, ProductStatus, ProductImage, ProductVariant,
        Attribute, ProductAttributeValue, ProductQuestion, FlashSale, StockMovement,
        CartItem, Favorite, ProductView, ProductSubscription,
        Order, OrderStatus, OrderItem, SubOrder, SubOrderStatus, Payment, PaymentGateway,
        PaymentStatus, FiscalReceipt, FiscalReceiptType, FiscalReceiptStatus, DeliveryInfo,
        Transaction, TransactionType, BalanceTransaction, BalanceTransactionType,
        Review, ReviewStatus, ReviewReply, ReviewVote, ReviewPhoto,
        ReturnRequest, ReturnRequestStatus, Coupon, SellerCoupon, DiscountType,
        Notification, NotificationType, ChatThread, ChatMessage, ChatTemplate,
        PayoutRequest, PayoutRequestStatus, HomepageBanner, Address,
        WishlistCollection, WishlistItem, Referral, ReferralType, ReferralReward,
        Report, ReportStatus, AuditLog, FeatureFlag, VerificationCode, VerificationPurpose,
        SmsLog, PasswordResetToken,
        SupportTicket, SupportMessage, SupportTicketStatus, SupportTicketPriority,
        PaidFeature, Promotion, PromotionStatus, AdWalletTransaction,
        PromoRule, PromoType, Bundle, BundleItem,
    )

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        # Idempotency guard
        if (await db.execute(select(User).where(User.email == "seller@demo.local"))).scalar_one_or_none():
            print("  Demo data already present — skipping")
            return

        admin = (await db.execute(
            select(User).where(User.email == settings.FIRST_SUPERUSER_EMAIL)
        )).scalar_one_or_none()

        # ── Users: seller + buyer ────────────────────────────────────────────
        seller = User(
            email="seller@demo.local", password_hash=get_password_hash("demo12345"),
            full_name="Демо Продавец", role=UserRole.seller, phone="+79990000001",
            is_active=True, email_verified=True, balance=Decimal("3043.00"),
        )
        buyer = User(
            email="buyer@demo.local", password_hash=get_password_hash("demo12345"),
            full_name="Демо Покупатель", role=UserRole.buyer, phone="+79990000002",
            is_active=True, email_verified=True, bonus_balance=Decimal("100.00"),
        )
        support_agent = User(
            email="support@demo.local", password_hash=get_password_hash("demo12345"),
            full_name="Демо Поддержка", role=UserRole.support, phone="+79990000003",
            is_active=True, is_staff=True, email_verified=True,
        )
        db.add_all([seller, buyer, support_agent])
        await db.flush()
        await ensure_referral_code(seller, db)
        await ensure_referral_code(buyer, db)

        # ── Shop + requisites + subscription ─────────────────────────────────
        shop = Shop(
            owner_id=seller.id, name="Демо-Маркет", description="Демонстрационный магазин.",
            tagline="Лучшие демо-товары", contact_email="shop@demo.local",
            contact_phone="+79990000001", status=ShopStatus.active, is_active=True,
        )
        db.add(shop)
        await db.flush()

        db.add(SellerRequisites(
            shop_id=shop.id, tax_regime=TaxRegime.individual, legal_name="ИП Демонстрационный И.И.",
            inn="500100732259", ogrn="312500000000012", legal_address="г. Москва, ул. Демо, д. 1",
            vat_code=1, tax_system_code=2, bank_account="40802810500000000001",
            bank_name="ДЕМО-БАНК", bik="044525225", corr_account="30101810400000000225",
        ))

        default_plan = (await db.execute(
            select(SellerPlan).where(SellerPlan.is_default == True)  # noqa: E712
        )).scalar_one_or_none()
        if default_plan:
            db.add(SellerSubscription(
                shop_id=shop.id, plan_id=default_plan.id, status=SubscriptionStatus.active,
                current_period_end=now + timedelta(days=30), auto_renew=True,
            ))

        category = (await db.execute(
            select(Category).where(Category.slug == "electronics")
        )).scalar_one_or_none()
        cat_id = category.id if category else 1

        # ── Products (two, so co-purchase/recommendations are meaningful) ─────
        p1 = Product(
            shop_id=shop.id, category_id=cat_id, title="Демо-наушники беспроводные",
            slug="demo-headphones", description="Демонстрационные наушники.", price=Decimal("2990.00"),
            compare_at_price=Decimal("3990.00"), quantity=50, status=ProductStatus.active,
            views_count=12,
        )
        p2 = Product(
            shop_id=shop.id, category_id=cat_id, title="Демо-чехол защитный",
            slug="demo-case", description="Демонстрационный чехол.", price=Decimal("590.00"),
            quantity=200, status=ProductStatus.active, views_count=5,
        )
        db.add_all([p1, p2])
        await db.flush()

        db.add_all([
            ProductImage(product_id=p1.id, url="https://picsum.photos/seed/demo1/600", is_main=True),
            ProductImage(product_id=p2.id, url="https://picsum.photos/seed/demo2/600", is_main=True),
        ])
        variant = ProductVariant(product_id=p1.id, sku="DEMO-HP-BLK", name="Чёрный", quantity=30)
        db.add(variant)

        brand_attr = (await db.execute(
            select(Attribute).where(Attribute.slug == "brand")
        )).scalar_one_or_none()
        if brand_attr:
            db.add(ProductAttributeValue(product_id=p1.id, attribute_id=brand_attr.id, value="DemoSound"))

        db.add(FlashSale(
            product_id=p2.id, shop_id=shop.id, discount_percent=Decimal("20.00"),
            starts_at=now - timedelta(hours=1), ends_at=now + timedelta(days=3), is_active=True,
        ))
        db.add(StockMovement(
            product_id=p1.id, change=50, reason="initial", quantity_after=50, note="Стартовый остаток",
        ))
        db.add(ProductQuestion(
            product_id=p1.id, user_id=buyer.id, question="Какое время автономной работы?",
            answer="До 20 часов.", answered_by_id=seller.id, answered_at=now,
        ))

        # ── Buyer activity: cart, favorite, view, price subscription ─────────
        db.add(CartItem(user_id=buyer.id, product_id=p2.id, quantity=1))
        db.add(Favorite(user_id=buyer.id, product_id=p1.id))
        db.add(ProductView(user_id=buyer.id, product_id=p1.id))
        from app.models.models import ShopFollow
        db.add(ShopFollow(user_id=buyer.id, shop_id=shop.id))
        db.add(ProductSubscription(
            user_id=buyer.id, product_id=p2.id, kind="price", target_price=Decimal("499.00"),
        ))

        # ── Order: buyer buys BOTH products in one completed order ───────────
        subtotal = Decimal("3580.00")
        delivery = Decimal("300.00")
        order = Order(
            buyer_id=buyer.id, subtotal=subtotal, delivery_cost=delivery,
            total_price=subtotal + delivery, platform_fee=Decimal("537.00"),
            seller_net=Decimal("3043.00"), commission_percent_used=Decimal("15.00"),
            status=OrderStatus.completed, delivery_address="г. Москва, ул. Покупателя, д. 5, кв. 10",
        )
        db.add(order)
        await db.flush()

        sub_order = SubOrder(
            order_id=order.id, shop_id=shop.id, status=SubOrderStatus.completed,
            tracking_number="DEMOTRACK123", delivery_service="cdek", carrier_uuid="demo-uuid",
        )
        db.add(sub_order)
        await db.flush()

        oi1 = OrderItem(
            order_id=order.id, product_id=p1.id, shop_id=shop.id, sub_order_id=sub_order.id,
            quantity=1, price_at_time=Decimal("2990.00"), commission_percent_used=Decimal("15.00"),
            platform_fee=Decimal("448.50"), seller_net=Decimal("2541.50"), payout_status="paid",
        )
        oi2 = OrderItem(
            order_id=order.id, product_id=p2.id, shop_id=shop.id, sub_order_id=sub_order.id,
            quantity=1, price_at_time=Decimal("590.00"), commission_percent_used=Decimal("15.00"),
            platform_fee=Decimal("88.50"), seller_net=Decimal("501.50"), payout_status="paid",
        )
        db.add_all([oi1, oi2])
        await db.flush()

        payment = Payment(
            order_id=order.id, gateway=PaymentGateway.yookassa, gateway_payment_id="demo-pay-001",
            amount=order.total_price, status=PaymentStatus.succeeded, paid_at=now,
        )
        db.add(payment)
        await db.flush()

        receipt_items = [
            {"description": "Демо-наушники беспроводные", "quantity": "1",
             "amount": {"value": "2990.00", "currency": "RUB"}, "vat_code": 1,
             "payment_subject": "commodity", "payment_mode": "full_prepayment"},
            {"description": "Демо-чехол защитный", "quantity": "1",
             "amount": {"value": "590.00", "currency": "RUB"}, "vat_code": 1,
             "payment_subject": "commodity", "payment_mode": "full_prepayment"},
            {"description": "Доставка", "quantity": "1",
             "amount": {"value": "300.00", "currency": "RUB"}, "vat_code": 1,
             "payment_subject": "service", "payment_mode": "full_prepayment"},
        ]
        db.add(FiscalReceipt(
            order_id=order.id, payment_id=payment.id, type=FiscalReceiptType.income,
            status=FiscalReceiptStatus.succeeded, customer_contact="buyer@demo.local",
            total=order.total_price, tax_system_code=2, items_json=json.dumps(receipt_items, ensure_ascii=False),
            fiscal_document_number="100500", fiscal_storage_number="9999078900001234",
            fiscal_attribute="1234567890", registered_at=now,
        ))
        db.add(DeliveryInfo(
            order_id=order.id, delivery_service="cdek", tracking_number="DEMOTRACK123",
            cost=delivery, estimated_days=3, city_from="Москва", city_to="Москва",
            address=order.delivery_address, shipped_at=now - timedelta(days=2), delivered_at=now,
        ))
        db.add(Transaction(
            user_id=buyer.id, type=TransactionType.order_payment, amount=order.total_price,
            order_id=order.id, description="Оплата заказа", balance_after=Decimal("0.00"),
        ))
        db.add(BalanceTransaction(
            user_id=seller.id, change=Decimal("3043.00"), type=BalanceTransactionType.credit,
            reference_type="order", reference_id=order.id, description="Выручка по заказу",
            balance_after=Decimal("3043.00"),
        ))

        # ── Review (verified) + reply + vote + photo ─────────────────────────
        review = Review(
            user_id=buyer.id, product_id=p1.id, rating=5, text="Отличные наушники, рекомендую!",
            status=ReviewStatus.approved, is_verified_purchase=True, order_id=order.id,
            helpful_count=1, moderated_by_id=admin.id if admin else None, moderated_at=now,
        )
        db.add(review)
        await db.flush()
        db.add(ReviewReply(review_id=review.id, seller_id=seller.id, text="Спасибо за отзыв!"))
        if admin:
            db.add(ReviewVote(review_id=review.id, user_id=admin.id))
        db.add(ReviewPhoto(review_id=review.id, url="https://picsum.photos/seed/demorev/400"))

        # ── Return request on the order item ─────────────────────────────────
        db.add(ReturnRequest(
            order_item_id=oi2.id, buyer_id=buyer.id, shop_id=shop.id, quantity=1,
            reason="Не подошёл размер", status=ReturnRequestStatus.requested,
        ))

        # ── Coupons (platform + shop) ────────────────────────────────────────
        db.add(Coupon(
            code="WELCOME10", discount_type=DiscountType.percent, discount_value=Decimal("10.00"),
            valid_from=now - timedelta(days=1), valid_until=now + timedelta(days=30),
            max_uses=100, min_order_amount=Decimal("1000.00"), is_active=True,
        ))
        db.add(SellerCoupon(
            shop_id=shop.id, code="DEMOSHOP5", discount_type=DiscountType.percent,
            discount_value=Decimal("5.00"), min_order_amount=Decimal("500.00"),
            usage_limit=50, is_active=True, expires_at=now + timedelta(days=60),
        ))

        # ── Notifications, chat, templates ───────────────────────────────────
        db.add(Notification(
            user_id=buyer.id, type=NotificationType.order_status, title="Заказ доставлен",
            body="Ваш заказ #1 доставлен.", link="/orders/1",
        ))
        thread = ChatThread(buyer_id=buyer.id, shop_id=shop.id)
        db.add(thread)
        await db.flush()
        db.add_all([
            ChatMessage(thread_id=thread.id, sender_id=buyer.id, text="Здравствуйте! Есть в наличии?"),
            ChatMessage(thread_id=thread.id, sender_id=seller.id, text="Да, в наличии!", is_read=True),
        ])
        db.add(ChatTemplate(shop_id=shop.id, title="Приветствие", body="Здравствуйте! Чем можем помочь?"))

        # ── Payout, banner, address, wishlist ────────────────────────────────
        db.add(PayoutRequest(
            user_id=seller.id, amount=Decimal("1000.00"), status=PayoutRequestStatus.pending,
            payout_details="Счёт 40802810500000000001",
        ))
        db.add(HomepageBanner(
            title="Добро пожаловать в Демо-Маркет", subtitle="Скидки на демо-товары",
            image_url="https://picsum.photos/seed/demobanner/1200/300", link="/catalog", is_active=True,
        ))
        db.add(Address(
            user_id=buyer.id, label="Дом", full_name="Демо Покупатель", phone="+79990000002",
            city="Москва", street="ул. Покупателя", building="5", apartment="10",
            postal_code="101000", is_default=True,
        ))
        collection = WishlistCollection(user_id=buyer.id, name="Хочу купить", is_public=False)
        db.add(collection)
        await db.flush()
        db.add(WishlistItem(collection_id=collection.id, product_id=p2.id))

        # ── Referral (admin referred buyer) + reward ─────────────────────────
        if admin:
            referral = Referral(
                referrer_id=admin.id, referred_user_id=buyer.id, type=ReferralType.buyer,
                code=admin.referral_code or "DEMOREF", reward_paid=True,
            )
            db.add(referral)
            await db.flush()
            db.add(ReferralReward(
                referral_id=referral.id, amount=Decimal("200.00"), type=ReferralType.buyer, status="paid",
            ))

        # ── Report, audit, feature flag ──────────────────────────────────────
        db.add(Report(
            reporter_id=buyer.id, target_type="product", target_id=p2.id,
            reason="Демо-жалоба для теза", status=ReportStatus.open,
        ))
        db.add(AuditLog(
            actor_id=admin.id if admin else None, action="seed_demo", entity_type="system",
            detail="Демо-данные созданы сид-скриптом",
        ))
        db.add(FeatureFlag(
            key="demo_feature", description="Демонстрационный флаг", is_enabled=True, rollout_percent=100,
        ))

        # ── Security-ish artifacts ───────────────────────────────────────────
        db.add(VerificationCode(
            user_id=buyer.id, code="123456", purpose=VerificationPurpose.email,
            destination="buyer@demo.local", expires_at=now + timedelta(minutes=15), used=True,
        ))
        db.add(SmsLog(
            phone="+79990000002", purpose="phone_verification", text_preview="Ваш код: ******",
            status="sent", smsc_id="demo-sms-1", cost=Decimal("2.50"),
        ))
        db.add(PasswordResetToken(
            user_id=buyer.id, token="demo-reset-token-0001",
            expires_at=now - timedelta(hours=1), used=True,
        ))

        # ── Support ticket with a short conversation ─────────────────────────
        ticket = SupportTicket(
            user_id=buyer.id, subject="Где мой заказ?", category="order",
            status=SupportTicketStatus.in_progress, priority=SupportTicketPriority.normal,
            assigned_to_id=support_agent.id, first_response_at=now,
            last_message_at=now,
        )
        db.add(ticket)
        await db.flush()
        db.add_all([
            SupportMessage(ticket_id=ticket.id, sender_id=buyer.id, is_staff=False,
                           text="Здравствуйте! Когда придёт мой заказ #1?", read_by_user=True, read_by_staff=True),
            SupportMessage(ticket_id=ticket.id, sender_id=support_agent.id, is_staff=True,
                           text="Здравствуйте! Заказ уже в пути, ожидайте сегодня.", read_by_staff=True),
        ])

        # ── Paid features + a demo homepage promotion (auction winner) ───────
        from app.services import promotion_service
        await promotion_service.ensure_default_features(db)
        await db.flush()
        homepage_feature = (await db.execute(
            select(PaidFeature).where(PaidFeature.key == "homepage_top")
        )).scalar_one_or_none()
        if homepage_feature:
            shop.ad_balance = Decimal("1750.00")
            db.add_all([
                AdWalletTransaction(shop_id=shop.id, change=Decimal("2000.00"), kind="topup",
                                    description="Пополнение (ad_1000)", balance_after=Decimal("2000.00")),
                AdWalletTransaction(shop_id=shop.id, change=Decimal("-250.00"), kind="spend",
                                    description="Аукцион: Продвижение на главной", balance_after=Decimal("1750.00")),
            ])
            db.add(Promotion(
                shop_id=shop.id, product_id=p1.id, feature_id=homepage_feature.id,
                feature_key=homepage_feature.key, placement="homepage",
                bid_amount=Decimal("250.00"), status=PromotionStatus.active,
                starts_at=now, last_charged_at=now, total_spent=Decimal("250.00"),
                impressions=320, clicks=24,
            ))

        # ── Расширенные акции: объёмная скидка + набор ───────────────────────
        import json as _json
        db.add(PromoRule(
            shop_id=shop.id, title="Скидка за объём: от 2 шт −10%", type=PromoType.volume,
            is_active=True, product_id=p1.id,
            tiers_json=_json.dumps([{"min_qty": 2, "percent": 10}, {"min_qty": 5, "percent": 15}]),
        ))
        bundle = Bundle(
            shop_id=shop.id, title="Наушники + чехол", description="Выгодный комплект",
            bundle_price=Decimal("3290.00"), is_active=True,
        )
        db.add(bundle)
        await db.flush()
        db.add_all([
            BundleItem(bundle_id=bundle.id, product_id=p1.id, quantity=1),
            BundleItem(bundle_id=bundle.id, product_id=p2.id, quantity=1),
        ])

        # ── Демо-спор (в арбитраже) ──────────────────────────────────────────
        from app.models.models import Dispute, DisputeMessage, DisputeStatus, DisputeResolution
        dispute = Dispute(
            order_id=order.id, order_item_id=oi2.id, buyer_id=buyer.id, shop_id=shop.id,
            opened_by="buyer", subject="Товар пришёл повреждённым",
            reason="Чехол приехал с царапинами, прошу частичный возврат.",
            status=DisputeStatus.in_mediation, resolution=DisputeResolution.none,
            mediator_id=support_agent.id, last_message_at=now,
        )
        db.add(dispute)
        await db.flush()
        db.add_all([
            DisputeMessage(dispute_id=dispute.id, sender_id=buyer.id, sender_role="buyer",
                           text="Чехол приехал с царапинами, прошу частичный возврат."),
            DisputeMessage(dispute_id=dispute.id, sender_id=seller.id, sender_role="seller",
                           text="Здравствуйте! Готовы обсудить компенсацию."),
            DisputeMessage(dispute_id=dispute.id, sender_id=buyer.id, sender_role="system",
                           text="Спор передан на рассмотрение арбитражу платформы."),
        ])

        # ── Подарочные сертификаты + промо-баланс ────────────────────────────
        from app.models.models import GiftCertificate, GiftCertificateStatus, PromoBalanceTransaction
        buyer.promo_balance = Decimal("300.00")
        db.add_all([
            GiftCertificate(code="GIFT-DEMO-2025", amount=Decimal("300.00"),
                            status=GiftCertificateStatus.redeemed, redeemed_by_id=buyer.id,
                            redeemed_at=now, message="С днём рождения!"),
            GiftCertificate(code="GIFT-PROMO-NEW1", amount=Decimal("500.00"),
                            status=GiftCertificateStatus.active, message="Промо-кампания"),
            PromoBalanceTransaction(user_id=buyer.id, change=Decimal("300.00"), kind="gift_redeem",
                                    description="Активация сертификата GIFT-DEMO-2025",
                                    balance_after=Decimal("300.00")),
        ])

        # ── Программа лояльности: уровни + покупатель на «Серебре» ────────────
        from app.services import loyalty_tier_service
        from app.models.models import LoyaltyTier
        await loyalty_tier_service.ensure_default_tiers(db)
        await db.flush()
        silver = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.key == "silver"))).scalar_one_or_none()
        if silver:
            buyer.loyalty_tier_id = silver.id
            buyer.qualifying_spend = Decimal("45000.00")
            buyer.tier_since = now
            buyer.last_qualifying_order_at = now

        await db.commit()

        # ── Derived data: ratings + co-purchase recommendations ──────────────
        from app.services import rating_service, recommendation_service
        await rating_service.recalculate_for_product(db, p1.id)
        await rating_service.recalculate_for_product(db, p2.id)
        await recommendation_service.rebuild_co_purchase(db)
        await db.commit()

        print("✓ Demo data created (seller@demo.local / buyer@demo.local, пароль demo12345)")


if __name__ == "__main__":
    asyncio.run(seed())
