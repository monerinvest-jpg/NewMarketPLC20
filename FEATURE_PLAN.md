# Новый запрос (4 пункта): этикетки/отгрузка, фискализация, отзывы+рейтинг, рекомендации

## Блок 1 — Этикетки + отгрузка [DONE, в архиве]
- delivery_service: ShipmentResult, create_shipment/get_label в базовом классе
- CDEK: полная API 2.0 отгрузка (POST /orders → uuid → cdek_number, /print/orders → PDF)
- mock-fallback (детерминированный трек) когда нет ключей
- label_service: своя A6 PDF-этикетка с Code128 штрихкодом (reportlab) — fallback
- SubOrder.carrier_uuid; миграция 51↔51
- Эндпоинты: POST /sub-orders/{id}/shipment, GET /sub-orders/{id}/label
- SellerOrders: модалка «через API / вручную», выбор перевозчика, кнопка «Этикетка»

## Блок 2 — Фискализация чеков (54-ФЗ/ОФД) [DONE, в архиве]
- Способ: встроенная фискализация ЮKassa (объект receipt в платеже/возврате)
- models: FiscalReceipt (+ enum FiscalReceiptType income/income_refund, FiscalReceiptStatus
  pending/succeeded/canceled/failed); SellerRequisites.vat_code + tax_system_code; миграция 52↔52
- config: FISCAL_ENABLED, FISCAL_VAT_CODE, FISCAL_TAX_SYSTEM_CODE, FISCAL_PAYMENT_SUBJECT,
  FISCAL_PAYMENT_MODE, FISCAL_AGENT_SCHEME (+ .env.example)
- fiscal_service: сборка receipt (customer email/phone, позиции с НДС/предмет/способ расчёта,
  строка доставки как service, per-seller СНО, агентская схема supplier+agent_type),
  снапшот чека, применение receipt_registration из вебхука
- payment_service: create_payment(receipt=), refund_payment(receipt=), create_standalone_receipt
  (POST /receipts для повторной отправки)
- orders.py: чек прихода при создании платежа + запись FiscalReceipt(pending);
  вебхук обновляет статус регистрации; возврат прихода при отмене оплаченного заказа
- return_service: чек возврата прихода при RMA-возврате (guarded)
- Эндпоинты: GET /orders/{id}/receipts (покупатель/продавец/стафф);
  admin: GET /admin/fiscal/receipts (фильтры+счётчики), GET /{id}, POST /{id}/retry
- Frontend: AdminFiscalReceipts.tsx (таблица+статистика+детали+повтор), меню «Фискальные чеки»;
  OrderDetailPage — блок «Кассовые чеки» со статусом; RequisitesFields — НДС + СНО

## Блок 3 — Верифицированные отзывы + рейтинг продавца [DONE, в архиве]
- Review: is_verified_purchase + order_id (привязка к завершённому заказу); миграция 53↔53
- Shop: reviews_count (рядом с rating, который раньше не пересчитывался)
- rating_service: единый пересчёт рейтинга товара И магазина (avg approved-отзывов по товарам
  магазина) + shop_rating_summary (среднее, число отзывов, verified_count, распределение 1–5)
- reviews.py: при создании отзыва ставится is_verified_purchase=True и order_id;
  recalculate_for_product (товар+магазин); фильтр verified_only в списке;
  GET /reviews/shop/{id}/summary
- admin.py: модерация/удаление отзыва теперь пересчитывают и рейтинг магазина (через rating_service)
- schemas: ReviewOut.is_verified_purchase, ShopOut.reviews_count, ShopRatingSummary
- Frontend: бейдж «Проверенная покупка» + чекбокс «только проверенные» (ProductPage);
  карточка рейтинга продавца с распределением по звёздам и счётчиком проверенных (ShopPage)

## Блок 4 — Рекомендации «с этим покупают» [DONE, в архиве]
- Был базовый эндпоинт (live co-purchase + фоллбэк по категории) — доведён до полноценного:
- ProductCoPurchase: материализованная таблица со-покупок (направленные пары + score);
  миграция 54↔54
- recommendation_service: rebuild_co_purchase (только заказы со статусом paid+, не pending/
  cancelled/refunded), get_product_recommendations (материализ. + фоллбэк по категории, порядок
  по релевантности), recommended_for_user (персонально по истории покупок + фоллбэк топ-рейтинг),
  cart_recommendations (по составу корзины)
- Эндпоинты: GET /products/{id}/recommendations (через сервис), GET /recommendations/for-me (auth),
  POST /recommendations/cart; admin POST /admin/recommendations/rebuild
- Celery: задача rebuild_recommendations + ночной beat (4:00)
- Frontend: RecommendationRow (переиспользуемый); «Рекомендуем вам» на главной (для авторизованных),
  «С этими товарами часто покупают» в корзине; блок на странице товара уже был
- ВСЕ 4 БЛОКА НОВОГО ЗАПРОСА ЗАВЕРШЕНЫ

# ═══ НОВЫЙ ЗАПРОС: Поддержка + Платное продвижение ═══

## Блок A — Поддержка пользователей [DONE, в архиве]
- Роль UserRole.support; RBAC: права users.view / support.handle / support.manage;
  ROLE_DEFAULT_PERMISSIONS (support → handle+view, moderator → ведёт поддержку); миграция 55↔55
- Модели SupportTicket (статус/приоритет/назначение/время первого ответа) + SupportMessage (чат)
- dep get_current_support_staff (support/moderator/superadmin/право support.handle)
- Эндпоинты /support: пользователь (создать/список/тикет/сообщение/закрыть);
  стафф (очередь с фильтрами, тикет, ответ, статус/приоритет/назначение, assign-me, СТАТИСТИКА,
  read-only карточка пользователя/продавца). Назначение на другого агента — только support.manage.
- Супер-админ: смена роли (вкл. support) и редактирование — через admin users + AdminModerators
- Frontend: SupportPage (пользователь — тикеты+чат), SupportDesk (стафф — очередь+чат+назначение+
  статистика+карточка клиента), роуты /support и /support-desk, пункты меню; AdminModerators
  управляет и модераторами, и агентами поддержки; роль «Поддержка» в AdminUsers
- Seed: агент support@demo.local + демо-обращение с перепиской

## Блок B — Платное продвижение магазина/товаров (аукцион) [DONE, в архиве]
- Enum PromotionStatus / PaidFeaturePricing; модели PaidFeature (каталог фич: цена, период,
  слоты, вкл/выкл) и Promotion (ставка/покупка продавца); миграция 56↔56
- promotion_service: каталог по умолчанию (homepage_top аукцион 5 слотов, category_top аукцион,
  product_highlight фикс), списание с баланса магазина, place_promotion (фикс — сразу оплата+актив;
  аукцион — ставка в очередь), settle_auction/settle_all (ранжирование ставок, суточное списание
  победителей, демоут проигравших в outbid), active_homepage_products, auction_standing
- Эндпоинты: seller (/seller/promotions: features, мои, standing, создать, отменить),
  admin (/admin/paid-features GET+PATCH, /admin/promotions, /admin/promotions/settle),
  public (/promotions/homepage — победители для главной)
- Celery: settle_promotions + ночной beat (00:30)
- Frontend: SellerPromotion (карточки фич, ставка/покупка, мои продвижения, подсказка по аукциону),
  AdminPaidFeatures (правка цены/слотов/тумблер + обзор продвижений + ручной пересчёт),
  ряд «Рекомендуемые товары · Реклама» на главной; пункты меню
- Seed: каталог фич + активное демо-продвижение товара на главной
- ОБА БЛОКА НОВОГО ЗАПРОСА (поддержка + продвижение) ЗАВЕРШЕНЫ

## Доработки (по запросу) [DONE, в архиве]
1. Рекламный кошелёк: Shop.ad_balance + AdWalletTransaction; пакеты пополнения (с бонусом);
   продвижение списывается с рекламного кошелька, а не с основного баланса; миграция 57↔57
   - Эндпоинты: GET /seller/promotions/wallet, POST /seller/promotions/wallet/topup
   - Frontend: карточка кошелька с балансом, пакетами и историей в SellerPromotion
2. Уведомление о перебитой ставке: при демоуте active→outbid в settle_auction шлём NotificationType.system
3. SLA и эскалации в поддержке: SupportTicket.escalation_level + is_overdue; настройки SLA в config;
   support_service.sla_sweep (эскалация приоритета + авто-назначение наименее загруженному агенту);
   Celery support_sla_sweep (ежечасно) + ручной POST /support/staff/sla-sweep (только support.manage);
   overdue в статистике, фильтр «только просроченные», бейдж SLA и кнопка проверки в SupportDesk

# ═══ БОЛЬШОЙ ЗАПРОС: развитие платформы (всё, кроме мобильного — оно в самом конце) ═══
# Делаем по блоку за заход, с миграцией/сидом/пересборкой архива.

## Блок 1 — Подписка на магазины + лента обновлений [DONE, в архиве]
- ShopFollow + NotificationType.shop_update; миграция 58↔58
- shop_follow_service: follow/unfollow/feed/notify_followers; уведомления при публикации товара и старте распродажи
- Эндпоинты: /shops/{id}/follow(POST/DELETE), /follow-status, /shops/following, /shops/feed
- Frontend: кнопка «Подписаться» + счётчик на ShopPage; страница «Мои подписки» (магазины + лента новинок); пункт меню
- Seed: демо-покупатель подписан на демо-магазин
## Блок 2 — Расширенные акции (N+1, объёмные скидки, наборы) [DONE, в архиве]
- PromoType enum; PromoRule (nplus/volume, scope товар/категория/весь магазин) + Bundle/BundleItem; миграция 61↔61
- promo_rules_service: compute_nplus/compute_volume/compute_promotions (правила+наборы), bundles_for_product
- Эндпоинты: seller CRUD /seller/promo-rules и /seller/bundles; public /products/{id}/bundles, /shops/{id}/promos; GET /cart/summary
- Интеграция: авто-скидка свёрнута в discount при создании заказа; превью в корзине
- Frontend: SellerPromoRules (вкладки акции+наборы), строка «Скидка по акциям» в корзине, блок «Выгодные наборы» на странице товара
- Seed: демо объёмная скидка на p1 + набор p1+p2
## Блок 3 — Аналитика рекламы продавца (ROI) [DONE, в архиве]
- Promotion.impressions/clicks; миграция 61↔61 (колонки)
- promotion_service: record_event, active_homepage_promotions (с id), _attributed_revenue (выручка по промо-товару за период), seller_analytics (CTR/CPC/ROI + итоги)
- Эндпоинты: /promotions/homepage (теперь с promotion_id), POST /promotions/{id}/event, GET /seller/promotions/analytics
- Frontend: показы/клики с главной (recordEvent), раздел «Аналитика рекламы (ROI)» в SellerPromotion (карточки итогов + таблица по кампаниям)
- Seed: демо-промо с показами/кликами
## Блок 4 — Арбитраж споров [DONE, в архиве]
- DisputeStatus/DisputeResolution; Dispute + DisputeMessage (чат); миграция 63↔63
- dispute_service: open/message/escalate/resolve (+рефанд: кредит покупателю, дебет продавцу), role_in_dispute
- Эндпоинты: покупатель (открыть/список/чат/эскалация/отмена), продавец (список/concede=полный возврат), медиатор (очередь/assign/resolve/stats)
- Доступ через role_in_dispute (buyer/seller/mediator); медиатор = персонал поддержки
- Frontend: DisputeThread (общий чат), DisputesPage (покупатель), SellerDisputes, DisputeDesk (арбитр); роуты и меню
- Seed: демо-спор в арбитраже с перепиской
## Блок 5 — Подарочные сертификаты + промо-баланс [DONE, в архиве]
- User.promo_balance, Order.promo_used; GiftCertificate + PromoBalanceTransaction; миграция 65↔65 (+2 колонки)
- gift_service: purchase (с осн. баланса), issue (админ), redeem (на промо-баланс), spend_promo (на чекауте), overview
- Интеграция: промо-баланс авто-списывается при оформлении заказа (order.promo_used)
- Эндпоинты: /gift-certificates (purchase/redeem/promo-balance), /admin/gift-certificates (issue/list)
- Frontend: GiftCertificatesPage (баланс+активация+покупка+история), AdminGiftCertificates (выпуск+список); меню
- Seed: промо-баланс 300₽ + активированный и промо-сертификаты
## Блок 6 — Программа лояльности с уровнями [DONE, в архиве]
- LoyaltyTier (НАСТРАИВАЕТСЯ В АДМИНКЕ: порог, кэшбэк%, перки, free_shipping, retention_days, цвет)
- User: loyalty_tier_id/qualifying_spend/tier_since/last_qualifying_order_at; миграция 66↔66 (+4 кол.)
- loyalty_tier_service: tier_for_spend, recompute, on_order_completed (накопление+апгрейд), cashback%, free_shipping, decay_sweep (распад по неактивности), user_status (прогресс+дни до понижения)
- Интеграция: кэшбэк по % уровня (в award_cashback_for_order), бесплатная доставка на чекауте
- Эндпоинты: /loyalty/me, /loyalty/tiers; /admin/loyalty-tiers CRUD; Celery loyalty_decay (ежедн.)
- Frontend: LoyaltyPage (уровень, прогресс, обратный отсчёт до понижения, перки, лестница), AdminLoyaltyTiers (CRUD); меню
- Seed: дефолтные уровни + покупатель на «Серебре» (45000₽)
# ════════════════════════════════════════════════════════════════════════
# СОГЛАСОВАННАЯ ДОРОЖНАЯ КАРТА (2026-06-29) — решения утверждены, реализуем
# Порядок: 5 (фундамент) → 7 → 3 → 1 → 4 → 2 → 6. Деплой НЕ делаем; коммит+пуш по задачам.
# ════════════════════════════════════════════════════════════════════════

## Блок 0 — Полное редактирование в админке [DONE]
- ShopAdminUpdate расширен (name/description/tagline/контакты/accent_color + комиссия/активность) + аудит; AdminShopDetail: модалка редактирования + кнопки модерации.
- Заказы: OrderStatusUpdate +delivery_address; update_order_admin правит адрес/трек, отмена/возврат через order_reversal_service.restore_order (сток+бонусы+промо+реф+entitlements+рефанд продавцам), гард двойного завершения/реверса, аудит; AdminOrders — редактируемые адрес/трек.

## Блок 1 — KYC и бейджи доверия продавца [DONE]
- `seller_verification` (shop_id, status none/pending/verified/rejected, документы в приватном S3, проверяющий/дата); очередь в админке.
- `trust_badge` + уровень магазина. Verified — после проверки документов. VIP — (a) платно (платные возможности/подписка) или (b) за репутацию (rating≥X, reviews≥Y) — авто. Всё (пороги, цена, срок, обязательность KYC для вывода) настраивается в AdminSettings. Бейдж на карточке/странице магазина.

## Блок 2 — Email/Push-кампании (сегменты + рассылки) [DONE]
- `campaign_segment` (фильтр по роли/активности/тарифу/гео/реф-балансу → запрос по user), `campaign` (email/push/in-app, тема, HTML-шаблон, сегмент, расписание), `campaign_delivery` (статусы/открытия). Отправка через Celery батчами (лимиты Postbox). Раздел «Маркетинг → Рассылки»: предпросмотр размера сегмента, редактор, статистика. Обязательно: unsubscribe-токен + учёт согласий.

## Блок 3 — Мультипользовательские аккаунты магазина (сотрудники) [DONE]
- `shop_member` (shop_id, user_id, role owner/manager/staff, permissions JSON). Приглашение по email. Зависимость `require_shop_permission` вместо «owner==current_user» в seller-эндпоинтах. Раздел «Сотрудники» в кабинете продавца; выдача прав отображает доступные разделы (как в админке).

## Блок 4 — Мультидоставка (Почта России / Ozon / Яндекс) [DONE]
- Единый интерфейс гейтвея в delivery_service: quote/create_shipment/track/label. Сравнение тарифов на чекауте, выбор покупателем. Включение/приоритет служб — в админке (ключи уже в config.py). Старт: Почта России → Яндекс → Ozon.

## Блок 5 — Кэш (Redis) + оптимизация изображений + наблюдаемость [DONE]
- Кэш: декоратор @cached(ttl) на Redis для горячего чтения (витрина/категории/карточка/курсы валют) + инвалидация по событиям.
- Изображения: Celery-задача → webp + размеры (thumb/card/full), отдача из S3.
- Наблюдаемость: sentry-sdk во все сервисы (DSN из env), prometheus-fastapi-instrumentator → /metrics на каждом сервисе.

## Блок 6 — Мультиязычность (i18n), английский + переключатель [DONE — каркас ru/en, переводы наращиваются]
- Фронт: react-i18next (ru/en), переключатель в шапке рядом с валютой, синхрон с antd locale. Контент: переводы категорий (`category_translation`/JSONB) + опционально товара; иначе оригинал. Accept-Language → дефолт.

## Блок 7 — Метрики Grafana по всему проекту [DONE]
- Prometheus + Grafana как отдельный observability-контур: /metrics с каждого сервиса (из Блока 5), Kong Prometheus-плагин, exporters (node/PG/Redis). Дашборды в Grafana. В админке — раздел «Метрики» со встроенными дашбордами Grafana через iframe (read-only/signed-URL), доступ по праву analytics.view. Инфра Prometheus+Grafana — в Terraform/Ansible.

## Блок (отложено) — Второй платёжный шлюз/BNPL, B2B-режим, PWA/мобильное [ОТЛОЖЕНО до продакшена]
