import { useEffect, useState } from 'react'
import { Card, List, Button, Typography, Tag, Empty, Spin, message, Space } from 'antd'
import { DownloadOutlined, FileProtectOutlined } from '@ant-design/icons'
import { libraryApi } from '@/api'
import type { Entitlement, EntitlementFile } from '@/types'

const { Title, Text } = Typography

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

export default function MyDownloadsPage() {
  const [items, setItems] = useState<Entitlement[]>([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      setItems(await libraryApi.list())
    } catch {
      message.error('Не удалось загрузить покупки')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const download = async (productId: number, file: EntitlementFile) => {
    setDownloading(file.asset_id)
    try {
      const resp = await libraryApi.download(productId, file.asset_id)
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = file.file_name
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      message.error('Не удалось скачать файл')
    } finally {
      setDownloading(null)
    }
  }

  if (loading) {
    return <div className="flex justify-center py-20"><Spin size="large" /></div>
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <Title level={3}>
        <FileProtectOutlined className="mr-2" />
        Мои покупки
      </Title>
      <Text type="secondary">Цифровые товары и курсы, доступные мгновенно после оплаты.</Text>

      {items.length === 0 ? (
        <Empty className="mt-12" description="У вас пока нет цифровых покупок" />
      ) : (
        <div className="mt-6 space-y-4">
          {items.map((ent) => (
            <Card
              key={ent.id}
              title={
                <Space>
                  <span>{ent.product_title}</span>
                  {ent.revoked && <Tag color="red">доступ отозван</Tag>}
                </Space>
              }
              extra={<Text type="secondary">заказ #{ent.order_id}</Text>}
            >
              {ent.files.length === 0 ? (
                <Text type="secondary">Продавец ещё не приложил файлы.</Text>
              ) : (
                <List
                  dataSource={ent.files}
                  renderItem={(f) => (
                    <List.Item
                      actions={[
                        <Button
                          key="dl"
                          type="primary"
                          icon={<DownloadOutlined />}
                          loading={downloading === f.asset_id}
                          disabled={ent.revoked}
                          onClick={() => download(ent.product_id, f)}
                        >
                          Скачать
                        </Button>,
                      ]}
                    >
                      <List.Item.Meta
                        title={f.file_name}
                        description={formatSize(f.size_bytes)}
                      />
                    </List.Item>
                  )}
                />
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
