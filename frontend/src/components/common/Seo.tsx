import { Helmet } from 'react-helmet-async'

// Per-page <head> tags: title, description, Open Graph / Twitter cards and a
// canonical URL. SPA-rendered (no SSR yet), which search bots and messenger
// link-preview crawlers that execute JS will pick up; full SSR/prerender is a
// separate later step.
const SITE_NAME = '🪵 Маркетплейс'

export default function Seo({
  title,
  description,
  image,
  type = 'website',
}: {
  title?: string
  description?: string
  image?: string
  type?: 'website' | 'product' | 'article'
}) {
  const fullTitle = title ? `${title} — ${SITE_NAME}` : `${SITE_NAME} — товары ручной работы, цифровые товары и курсы`
  const desc =
    (description || 'Маркетплейс изделий ручной работы: уникальные товары от мастеров, цифровые продукты с мгновенной доставкой и онлайн-курсы.')
      .replace(/\s+/g, ' ')
      .slice(0, 200)
  const url = typeof window !== 'undefined' ? window.location.origin + window.location.pathname : ''

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={desc} />
      {url && <link rel="canonical" href={url} />}
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:type" content={type} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={desc} />
      {url && <meta property="og:url" content={url} />}
      {image && <meta property="og:image" content={image} />}
      <meta name="twitter:card" content={image ? 'summary_large_image' : 'summary'} />
    </Helmet>
  )
}
