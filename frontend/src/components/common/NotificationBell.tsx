import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge, Dropdown, Button, List, Typography, Empty, Spin } from 'antd'
import { BellOutlined } from '@ant-design/icons'
import { notificationsApi } from '@/api'
import type { Notification } from '@/types'
import dayjs from 'dayjs'

const { Text } = Typography

export default function NotificationBell() {
  const [count, setCount] = useState(0)
  const [items, setItems] = useState<Notification[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  const loadCount = () => {
    notificationsApi.unreadCount().then((r) => setCount(r.count)).catch(() => {})
  }

  useEffect(() => {
    loadCount()
    const interval = setInterval(loadCount, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleOpen = (o: boolean) => {
    setOpen(o)
    if (o) {
      setLoading(true)
      notificationsApi.list().then(setItems).finally(() => setLoading(false))
    }
  }

  const handleClick = async (n: Notification) => {
    if (!n.is_read) {
      await notificationsApi.markRead(n.id)
      loadCount()
    }
    setOpen(false)
    if (n.link) navigate(n.link)
  }

  const handleReadAll = async () => {
    await notificationsApi.markAllRead()
    setItems(items.map((i) => ({ ...i, is_read: true })))
    setCount(0)
  }

  const dropdownContent = (
    <div style={{ width: 360, background: '#fff', borderRadius: 8, boxShadow: '0 4px 16px rgba(0,0,0,0.12)', maxHeight: 480, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <Text strong>Уведомления</Text>
        {count > 0 && <Button type="link" size="small" onClick={handleReadAll}>Прочитать все</Button>}
      </div>
      {loading ? (
        <Spin style={{ display: 'block', margin: 24 }} />
      ) : items.length === 0 ? (
        <Empty description="Нет уведомлений" style={{ padding: 24 }} />
      ) : (
        <List
          dataSource={items}
          renderItem={(n) => (
            <List.Item
              style={{ padding: '12px 16px', cursor: 'pointer', background: n.is_read ? '#fff' : '#fff7ed' }}
              onClick={() => handleClick(n)}
            >
              <List.Item.Meta
                title={<Text style={{ fontSize: 14 }}>{n.title}</Text>}
                description={
                  <>
                    {n.body && <div style={{ fontSize: 12 }}>{n.body}</div>}
                    <Text type="secondary" style={{ fontSize: 11 }}>{dayjs(n.created_at).fromNow?.() || dayjs(n.created_at).format('DD.MM HH:mm')}</Text>
                  </>
                }
              />
            </List.Item>
          )}
        />
      )}
    </div>
  )

  return (
    <Dropdown
      open={open}
      onOpenChange={handleOpen}
      trigger={['click']}
      dropdownRender={() => dropdownContent}
      placement="bottomRight"
    >
      <Badge count={count} size="small">
        <Button type="text" icon={<BellOutlined style={{ fontSize: 18 }} />} />
      </Badge>
    </Dropdown>
  )
}
