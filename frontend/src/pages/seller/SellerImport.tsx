import { useEffect, useRef, useState } from 'react'
import {
  Card, Typography, Upload, Button, message, Alert, List, Select,
  Table, Tag, Space, Progress, Divider,
} from 'antd'
import { UploadOutlined, LinkOutlined, DownloadOutlined, ReloadOutlined } from '@ant-design/icons'
import { productsApi, categoriesApi, type VkMarketItem } from '@/api'
import type { Category } from '@/types'

const { Title, Paragraph, Text } = Typography

// ─── CSV import (as before) ──────────────────────────────────────────────────
function CsvImport() {
  const [result, setResult] = useState<{ created: number; errors: string[]; total_rows: number } | null>(null)
  const [uploading, setUploading] = useState(false)

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const res = await productsApi.importCsv(file)
      setResult(res)
      message.success(`Импортировано товаров: ${res.created}`)
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка импорта')
    } finally {
      setUploading(false)
    }
    return false
  }

  return (
    <>
      <Title level={4}>Импорт из CSV</Title>
      <Card>
        <Paragraph>
          Загрузите CSV-файл со столбцами: <Text code>title</Text>, <Text code>description</Text>,{' '}
          <Text code>price</Text>, <Text code>quantity</Text>, <Text code>category_id</Text>,{' '}
          <Text code>weight_g</Text> (необяз.), <Text code>compare_at_price</Text> (необяз.).
        </Paragraph>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          Первая строка — заголовки. Кодировка UTF-8 или Windows-1251. Товары попадут на модерацию, если она включена.
        </Paragraph>

        <Upload accept=".csv" showUploadList={false} beforeUpload={handleUpload}>
          <Button icon={<UploadOutlined />} loading={uploading} type="primary">Выбрать CSV-файл</Button>
        </Upload>
      </Card>

      {result && (
        <Card style={{ marginTop: 16 }}>
          <Alert
            type={result.errors.length === 0 ? 'success' : 'warning'}
            message={`Импортировано ${result.created} из ${result.total_rows} строк`}
            style={{ marginBottom: result.errors.length ? 12 : 0 }}
          />
          {result.errors.length > 0 && (
            <List
              size="small"
              header={<Text strong>Ошибки</Text>}
              dataSource={result.errors}
              renderItem={(err) => <List.Item><Text type="danger" style={{ fontSize: 12 }}>{err}</Text></List.Item>}
            />
          )}
        </Card>
      )}
    </>
  )
}

// ─── VK Market import ────────────────────────────────────────────────────────
function VkImport() {
  const [status, setStatus] = useState<{ configured: boolean; connected: boolean; community_name: string | null } | null>(null)
  const [communities, setCommunities] = useState<{ id: number; name: string }[]>([])
  const [communityId, setCommunityId] = useState<number | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [items, setItems] = useState<VkMarketItem[]>([])
  const [selected, setSelected] = useState<React.Key[]>([])
  const [loading, setLoading] = useState(false)
  const [job, setJob] = useState<{ state: string; progress?: { done: number; created: number; updated: number }; result?: any; error?: string } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval>>()

  const loadStatus = () => productsApi.vk.status().then(setStatus).catch(() => setStatus(null))

  useEffect(() => {
    loadStatus()
    categoriesApi.list().then(setCategories).catch(() => {})
    return () => clearInterval(pollRef.current)
  }, [])

  useEffect(() => {
    if (status?.connected) {
      productsApi.vk.communities().then(setCommunities).catch(() => setCommunities([]))
    }
  }, [status?.connected])

  const connect = async () => {
    try {
      const { url } = await productsApi.vk.authUrl()
      window.location.href = url
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Интеграция VK недоступна')
    }
  }

  const loadPreview = async () => {
    if (!communityId) return
    setLoading(true)
    try {
      const res = await productsApi.vk.preview(communityId)
      setItems(res.items)
      setSelected(res.items.map((i) => i.external_id))
      if (res.count === 0) message.info('В выбранном сообществе нет товаров')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Не удалось получить товары')
    } finally {
      setLoading(false)
    }
  }

  const startImport = async () => {
    if (!communityId || !categoryId) { message.warning('Выберите сообщество и категорию'); return }
    try {
      const all = selected.length === items.length
      const { task_id } = await productsApi.vk.startImport({
        community_id: communityId,
        category_id: categoryId,
        external_ids: all ? undefined : (selected as string[]),
      })
      setJob({ state: 'PENDING' })
      pollRef.current = setInterval(async () => {
        const st = await productsApi.vk.importStatus(task_id).catch(() => null)
        if (!st) return
        setJob(st)
        if (st.state === 'SUCCESS' || st.state === 'FAILURE') {
          clearInterval(pollRef.current)
          if (st.state === 'SUCCESS') message.success('Импорт завершён')
          loadStatus()
        }
      }, 2000)
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Не удалось запустить импорт')
    }
  }

  return (
    <>
      <Title level={4} style={{ marginTop: 32 }}>Импорт из VK (товары сообщества)</Title>
      <Card>
        {!status ? null : !status.configured ? (
          <Alert
            type="info" showIcon
            message="Интеграция VK не настроена"
            description="Администратору нужно зарегистрировать приложение на dev.vk.com и задать VK_APP_ID / VK_APP_SECRET / VK_REDIRECT_URI."
          />
        ) : !status.connected ? (
          <Space direction="vertical">
            <Paragraph style={{ marginBottom: 0 }}>
              Подключите свой аккаунт VK — мы покажем сообщества, где вы администратор,
              и перенесём товары из раздела «Товары» в ваш магазин (фото переезжают к нам).
            </Paragraph>
            <Button type="primary" icon={<LinkOutlined />} onClick={connect}>Подключить VK</Button>
          </Space>
        ) : (
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Space wrap>
              <Select
                placeholder="Сообщество"
                style={{ minWidth: 260 }}
                value={communityId ?? undefined}
                onChange={setCommunityId}
                options={communities.map((c) => ({ value: c.id, label: c.name }))}
              />
              <Button icon={<ReloadOutlined />} onClick={loadPreview} loading={loading} disabled={!communityId}>
                Показать товары
              </Button>
            </Space>

            {items.length > 0 && (
              <>
                <Table<VkMarketItem>
                  rowKey="external_id"
                  size="small"
                  dataSource={items}
                  pagination={{ pageSize: 10 }}
                  rowSelection={{ selectedRowKeys: selected, onChange: setSelected }}
                  columns={[
                    {
                      title: '', dataIndex: 'photo', width: 56,
                      render: (url) => url ? <img src={url} alt="" style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 6 }} /> : '🪵',
                    },
                    { title: 'Название', dataIndex: 'title', ellipsis: true },
                    { title: 'Цена', dataIndex: 'price', width: 110, render: (p) => `${parseFloat(p).toLocaleString('ru')} ₽` },
                    {
                      title: 'Наличие', dataIndex: 'available', width: 110,
                      render: (a) => a ? <Tag color="green">в наличии</Tag> : <Tag>нет</Tag>,
                    },
                  ]}
                />
                <Space wrap>
                  <Select
                    placeholder="Категория для импортируемых товаров"
                    style={{ minWidth: 300 }}
                    value={categoryId ?? undefined}
                    onChange={setCategoryId}
                    options={categories.map((c) => ({ value: c.id, label: c.name }))}
                  />
                  <Button
                    type="primary" icon={<DownloadOutlined />}
                    onClick={startImport}
                    disabled={selected.length === 0 || !categoryId || (job?.state === 'PENDING' || job?.state === 'PROGRESS')}
                  >
                    Импортировать ({selected.length})
                  </Button>
                </Space>
              </>
            )}

            {job && (
              <Card size="small">
                {job.state === 'SUCCESS' ? (
                  <Alert type="success" showIcon message={`Готово: создано ${job.result?.created ?? 0}, обновлено ${job.result?.updated ?? 0}`} />
                ) : job.state === 'FAILURE' ? (
                  <Alert type="error" showIcon message="Импорт завершился ошибкой" description={job.error} />
                ) : (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text type="secondary">Импортируем… {job.progress ? `обработано ${job.progress.done}` : ''}</Text>
                    <Progress percent={job.progress && selected.length ? Math.min(99, Math.round((job.progress.done / selected.length) * 100)) : 0} status="active" />
                  </Space>
                )}
              </Card>
            )}
          </Space>
        )}
      </Card>
    </>
  )
}

export default function SellerImport() {
  return (
    <div style={{ maxWidth: 860 }}>
      <Title level={3}>Импорт товаров</Title>
      <CsvImport />
      <Divider />
      <VkImport />
    </div>
  )
}
