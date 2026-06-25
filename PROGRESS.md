# Большой план: 20 пунктов + модерация магазина

## ВАЖНО О ПРОЦЕССЕ
Пересобирать архив ПОСЛЕ КАЖДОГО блока! В начале хода `rm -rf marketplace`
+ unzip перезаписывает рабочую папку из архива. Если архив не пересобран —
работа теряется. (Один раз так потеряли Блок 1, пришлось воссоздавать.)

## Блоки

### Блок 1 — Модерация магазина + фундамент моделей  [DONE, в архиве]
- ShopStatus enum (pending/active/rejected/suspended) ✓
- Shop.status + moderation_reason + business_hours ✓
- POST /admin/shops/{id}/moderate (+ audit + notify + email) ✓
- Фильтр /admin/shops?status= ✓
- get_shop требует status==active ✓ (новый магазин → pending)
- audit_service.py ✓
- User.permissions (RBAC-задел) ✓
- 9 таблиц: address, wishlist_collection, wishlist_item, product_view,
  stock_movement, flash_sale, audit_log, feature_flag, chat_template ✓
- Миграция 48↔48, FK, downgrade ✓
- Фронтенд: AdminShops (фильтр+модерация+модалка), SellerShopSettings (баннер статуса) ✓

### Блок 2 — Покупатель (1,2,4)  [DONE, в архиве]
- Адресная книга: CRUD /addresses (single-default логика), AddressBookPage,
  выбор сохранённого адреса в чекауте (заполняет delivery_address) ✓
- Коллекции желаний: CRUD /wishlists + items, WishlistsPage,
  кнопка "в коллекцию" на ProductPage (модалка выбора/создания) ✓
- История просмотров: ProductView upsert в get_product (get_current_user_optional),
  /recently-viewed, лента "Вы недавно смотрели" на HomePage ✓
- buyer_extra.py роутер зарегистрирован, схемы добавлены ✓
- Меню: "Мои коллекции", "Мои адреса" в дропдауне ✓

### Блок 3 — Продавец: склад(7) + акции(9) + массовое(8)  [DONE, в архиве]
- stock_service.py: record_movement (+ apply_to_stock flag), get_running_flash_sale, effective_price ✓
- StockMovement: запись при заказе/отмене/возврате/ручном; /seller/stock/adjust, /movements, /low ✓
- FlashSale: CRUD /seller/flash-sales, эффективная цена в ProductOut, отображение на ProductPage+каталоге ✓
- Массовое: bulk-price, bulk-status, export-csv; rowSelection в SellerProducts ✓
- SellerInventory.tsx, SellerFlashSales.tsx; меню Склад/Акции ✓
- seller_inventory.py зарегистрирован

### Блок 4 — Модерация (11,12,13)  [DONE, в архиве]
- moderation_service.py: авто-флаги (стоп-слова, дубли, аномальные цены, пустое описание) + приоритет ✓
- GET /admin/moderation/queue: pending-товары с флагами и приоритетом, сортировка ✓
- GET /admin/audit-log: просмотр с фильтрами (entity_type, action), actor_email ✓
- Аудит в moderate_product/bulk_moderate/process_payout/moderate_shop ✓
- Уведомление продавца при модерации товара ✓
- AdminModerationQueue.tsx (приоритеты/флаги/массовые), AdminAuditLog.tsx ✓
- Меню: Очередь модерации, Журнал действий ✓

### Блок 5 — Админ (14,15,16,17,18)  [DONE, в архиве]
- analytics_service.py: cohort_retention, lifetime_value, conversion_funnel, financial_reconciliation ✓
- rbac_service.py: ALL_PERMISSIONS, get/has_permission, serialize ✓
- Эндпоинты: /analytics/{cohorts,ltv,funnel,reconciliation}, /audit-log/export,
  /feature-flags CRUD, /permissions/catalog, /users/{id}/permissions ✓
- AdminCohortAnalytics (retention heatmap+LTV+воронка), AdminReconciliation,
  AdminFeatureFlags, экспорт аудит-лога, права в AdminModerators ✓
- Меню: Когорты и LTV, Реконсиляция, Feature flags ✓

### Блок 6 — Инфраструктура (3,5,6,10,19,20)  [DONE, в архиве]
- (3) Стэкинг бонусов+промокодов: cap на subtotal, защита от over-discount ✓
- (6) storage_service: локально или S3/MinIO, валидация типа/размера; /upload эндпоинт ✓
- (10) ChatTemplate CRUD /seller/chat-templates + /seller/business-hours; SellerChatTemplates.tsx ✓
- (19) pytest: tests/test_business_logic.py (комиссии, цены, slug, RBAC, приоритеты, скидки) ✓
- (20) search_service: MeiliSearch + ILIKE-фоллбэк; /products/search ✓
- (5) web-push: задел (in-app+email готовы; VAPID/SW не реализованы) — в README
- config: S3_*, MEILI_* опциональные настройки ✓
- ВСЕ 6 БЛОКОВ ЗАВЕРШЕНЫ

### Новый запрос · Блок 2 — Фискализация чеков (54-ФЗ)  [DONE, в архиве]
- Способ: встроенная фискализация ЮKassa (receipt в платеже/возврате; ОФД-регистрация на их стороне)
- models: FiscalReceipt + enums; SellerRequisites.vat_code/tax_system_code; миграция в 0001_initial ✓
- fiscal_service: build_receipt (НДС/предмет/способ расчёта, доставка=service, СНО, агентская схема),
  apply_registration (из вебхука), create_pending_receipt, retry-helpers ✓
- payment_service: receipt= в create_payment/refund_payment + create_standalone_receipt (/receipts) ✓
- orders.py: чек прихода при оплате, статус из receipt_registration в вебхуке, возврат прихода при отмене ✓
- return_service: чек возврата прихода при RMA ✓
- Эндпоинты: /orders/{id}/receipts; /admin/fiscal/receipts (list+counts), /{id}, /{id}/retry ✓
- Frontend: AdminFiscalReceipts.tsx + меню; OrderDetailPage блок чеков; RequisitesFields НДС/СНО ✓
- ВАЖНО: backend без зависимостей в окружении — проверено только py_compile; фронт без node_modules (typecheck не гонялся)

### Новый запрос · Блок 3 — Верифицированные отзывы + рейтинг продавца  [DONE, в архиве]
- Review.is_verified_purchase + order_id; Shop.reviews_count; в миграции 0001_initial ✓
- rating_service.py: recalculate_product_rating / recalculate_shop_rating / recalculate_for_product
  / shop_rating_summary (среднее, count, verified_count, распределение 1–5) ✓
- reviews.py: verified-флаг и order_id при создании; verified_only-фильтр; /reviews/shop/{id}/summary;
  общий пересчёт вместо локального ✓
- admin.py: модерация/удаление отзыва пересчитывают рейтинг товара И магазина ✓
- schemas: ReviewOut.is_verified_purchase, ShopOut.reviews_count, ShopRatingSummary ✓
- Frontend: бейдж + чекбокс «только проверенные» (ProductPage); карточка рейтинга продавца
  с распределением и verified-счётчиком (ShopPage) ✓
- Проверка: py_compile (без зависимостей в окружении); фронт без node_modules — typecheck не гонялся

### Новый запрос · Блок 4 — Рекомендации «с этим покупают»  [DONE, в архиве]
- ProductCoPurchase (материализованные направленные пары + score); в миграции 0001_initial ✓
- recommendation_service: rebuild_co_purchase (статусы paid+), get_product_recommendations,
  recommended_for_user, cart_recommendations ✓
- Эндпоинты: /products/{id}/recommendations (через сервис), /recommendations/for-me,
  /recommendations/cart; admin /admin/recommendations/rebuild ✓
- Celery: rebuild_recommendations + ночной beat (4:00) ✓
- Frontend: RecommendationRow; «Рекомендуем вам» (главная), «Часто покупают вместе» (корзина) ✓
- Тест: PURCHASED_STATUSES gating ✓
- Проверка: py_compile (без зависимостей в окружении); фронт без node_modules — typecheck не гонялся
- ИТОГ: все 4 блока нового запроса (этикетки/фискализация/отзывы+рейтинг/рекомендации) завершены

### Сидинг демо-данных  [DONE, в архиве]
- scripts/seed.py: к справочным данным (админ/категории/тарифы/атрибуты/валюты/настройки)
  добавлен seed_demo() — связная мини-история по строке на КАЖДУЮ оставшуюся таблицу (53 модели)
- Сценарий: продавец+магазин+реквизиты+подписка → 2 товара (картинки/вариант/атрибут/флэш-распродажа/
  движение склада/вопрос) → покупатель (корзина/избранное/просмотр/подписка на цену) → завершённый
  заказ из 2 позиций (суб-заказ/оплата succeeded/фискальный чек/доставка/транзакции) →
  верифицированный отзыв (+ответ/голос/фото) → возврат → купоны → чат+шаблон → выплата → баннер →
  адрес → вишлист → реферал+награда → жалоба → аудит → feature flag → коды/смс/reset-токен
- Рейтинги и co-purchase пересчитываются в конце через rating_service / recommendation_service
- Идемпотентно (guard по seller@demo.local). Логины демо: seller@demo.local / buyer@demo.local, пароль demo12345
- Запускается автоматически в docker-compose: alembic upgrade head && python scripts/seed.py

### Новый запрос · Блок A — Поддержка пользователей  [DONE, в архиве]
- Роль support + RBAC (users.view/support.handle/support.manage + дефолты ролей); в миграции ✓
- SupportTicket + SupportMessage; dep get_current_support_staff ✓
- /support: пользовательские и стафф-эндпоинты + статистика + read-only карточка клиента ✓
- Frontend: SupportPage, SupportDesk, роуты, меню, AdminModerators (мод+поддержка), роль в AdminUsers ✓
- Seed: support@demo.local + демо-тикет ✓
- Проверка: py_compile (без зависимостей); фронт без node_modules — typecheck не гонялся
- Следующий: Блок B — платное продвижение с аукционом

### Новый запрос · Блок B — Платное продвижение (аукцион)  [DONE, в архиве]
- PaidFeature (каталог: цена/период/слоты/тумблер) + Promotion (ставка/покупка); в миграции ✓
- promotion_service: дефолтный каталог, списание с баланса, place_promotion (фикс/аукцион),
  settle_auction/settle_all (ранжирование+суточное списание+демоут), homepage winners, standing ✓
- Эндпоинты: seller / admin (paid-features+settle) / public (homepage) ✓
- Celery: settle_promotions + ночной beat ✓
- Frontend: SellerPromotion, AdminPaidFeatures, ряд «Реклама» на главной, меню ✓
- Seed: каталог фич + активное демо-продвижение ✓
- Проверка: py_compile (без зависимостей); фронт без node_modules — typecheck не гонялся
- ИТОГ: поддержка + продвижение — оба блока готовы

### Доработки  [DONE, в архиве]
- Рекламный кошелёк (Shop.ad_balance + AdWalletTransaction + пакеты пополнения); списание промо с него ✓
- Уведомление продавцу при перебитой ставке (settle_auction) ✓
- SLA поддержки: escalation_level + is_overdue + sla_sweep (эскалация+авто-назначение) + Celery + ручной запуск;
  overdue в статах, фильтр и бейдж в SupportDesk ✓
- Проверка: py_compile (без зависимостей); фронт без node_modules — typecheck не гонялся

### Большой запрос · Блок 1 — Подписка на магазины + лента  [DONE, в архиве]
- ShopFollow + NotificationType.shop_update (в миграции); shop_follow_service ✓
- Уведомления подписчикам при новом товаре и флэш-распродаже ✓
- Эндпоинты follow/unfollow/status/following/feed ✓
- Frontend: кнопка подписки на ShopPage, страница «Мои подписки», меню ✓
- Seed: демо-подписка ✓
- Проверка: py_compile; фронт без node_modules — typecheck не гонялся
- Дальше: Блок 2 — расширенные акции

### Большой запрос · Блок 2 — Расширенные акции  [DONE, в архиве]
- PromoRule (nplus/volume) + Bundle/BundleItem; promo_rules_service (правила+наборы) ✓
- Эндпоинты seller CRUD + public bundles/promos + /cart/summary; интеграция в заказ ✓
- Frontend: SellerPromoRules, авто-скидка в корзине, наборы на странице товара ✓
- Seed: объёмная скидка + набор ✓
- Проверка: py_compile; фронт без node_modules — typecheck не гонялся
- Дальше: Блок 3 — аналитика рекламы продавца (ROI)

### Большой запрос · Блок 3 — Аналитика рекламы (ROI)  [DONE, в архиве]
- Promotion.impressions/clicks; record_event; seller_analytics (CTR/CPC/ROI + атрибуция выручки) ✓
- /promotions/homepage с promotion_id, POST /event, GET /seller/promotions/analytics ✓
- Frontend: трекинг показов/кликов на главной, раздел ROI в SellerPromotion ✓
- Проверка: py_compile; фронт без node_modules — typecheck не гонялся
- Дальше: Блок 4 — арбитраж споров

### Большой запрос · Блок 4 — Арбитраж споров  [DONE, в архиве]
- Dispute + DisputeMessage; dispute_service (open/escalate/resolve + рефанд) ✓
- Эндпоинты покупатель/продавец(concede)/медиатор(resolve); доступ через role_in_dispute ✓
- Frontend: DisputeThread + DisputesPage + SellerDisputes + DisputeDesk; роуты/меню ✓
- Seed: демо-спор ✓
- Проверка: py_compile; фронт без node_modules — typecheck не гонялся
- Дальше: Блок 5 — подарочные сертификаты + промо-баланс

### Большой запрос · Блок 5 — Подарочные сертификаты + промо-баланс  [DONE, в архиве]
- promo_balance/promo_used; GiftCertificate + PromoBalanceTransaction; gift_service ✓
- Авто-списание промо-баланса на чекауте; эндпоинты покупатель/админ ✓
- Frontend: GiftCertificatesPage, AdminGiftCertificates; меню ✓
- Seed: промо-баланс + сертификаты ✓
- Проверка: py_compile; фронт без node_modules — typecheck не гонялся
- Дальше: Блок 6 — программа лояльности с уровнями

### Большой запрос · Блок 6 — Программа лояльности с уровнями  [DONE, в архиве]
- LoyaltyTier (настраивается в админке) + поля лояльности у User; loyalty_tier_service ✓
- Кэшбэк по уровню, бесплатная доставка-перк, распад по неактивности (Celery), прогресс/обратный отсчёт ✓
- Эндпоинты /loyalty/* + /admin/loyalty-tiers CRUD; Frontend LoyaltyPage + AdminLoyaltyTiers ✓
- Seed: уровни + «Серебро» ✓
- Проверка: py_compile; фронт без node_modules — typecheck не гонялся
- Дальше: Блок 7 — KYC и бейджи доверия продавца
