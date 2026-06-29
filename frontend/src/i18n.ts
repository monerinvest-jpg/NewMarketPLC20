import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

// i18n foundation. UI strings live here under namespaced keys; pages adopt
// useTranslation() incrementally. Language is persisted (localStorage) and also
// drives the antd locale (see App.tsx).
const resources = {
  ru: {
    translation: {
      brand: 'Маркетплейс',
      nav: {
        catalog: 'Каталог',
        login: 'Войти',
        register: 'Регистрация',
        profile: 'Профиль',
        logout: 'Выйти',
      },
      header: { search: 'Поиск изделий ручной работы...' },
      footer: 'Маркетплейс изделий ручной работы',
      menu: {
        purchases: 'Покупки', orders: 'Мои заказы', downloads: 'Мои покупки',
        learning: 'Обучение', returns: 'Возвраты', disputes: 'Споры',
        lists: 'Избранное и коллекции', favorites: 'Избранное',
        bonus: 'Бонусы и баланс', referral: 'Реферальная программа',
        loyalty: 'Программа лояльности', account: 'Аккаунт', support: 'Поддержка',
        seller: 'Кабинет продавца', staff: 'Персоналу', admin: 'Админ-панель',
      },
      common: {
        save: 'Сохранить', cancel: 'Отмена', delete: 'Удалить', edit: 'Редактировать',
        add: 'Добавить', search: 'Поиск', loading: 'Загрузка...', back: 'Назад',
      },
    },
  },
  en: {
    translation: {
      brand: 'Marketplace',
      nav: {
        catalog: 'Catalog',
        login: 'Sign in',
        register: 'Sign up',
        profile: 'Profile',
        logout: 'Sign out',
      },
      header: { search: 'Search handmade goods...' },
      footer: 'Handmade goods marketplace',
      menu: {
        purchases: 'Purchases', orders: 'My orders', downloads: 'My purchases',
        learning: 'Learning', returns: 'Returns', disputes: 'Disputes',
        lists: 'Favorites & collections', favorites: 'Favorites',
        bonus: 'Bonuses & balance', referral: 'Referral program',
        loyalty: 'Loyalty program', account: 'Account', support: 'Support',
        seller: 'Seller cabinet', staff: 'Staff', admin: 'Admin panel',
      },
      common: {
        save: 'Save', cancel: 'Cancel', delete: 'Delete', edit: 'Edit',
        add: 'Add', search: 'Search', loading: 'Loading...', back: 'Back',
      },
    },
  },
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'ru',
    supportedLngs: ['ru', 'en'],
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'lang',
      caches: ['localStorage'],
    },
  })

export default i18n
