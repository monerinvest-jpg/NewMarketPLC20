import { useEffect, useState, useRef } from 'react'
import { Card, List, Input, Button, Typography, Empty, Spin, Badge, Avatar } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import { chatApi } from '@/api'
import type { ChatThreadSummary, ChatMessage } from '@/types'
import { useAuthStore } from '@/store/authStore'
import dayjs from 'dayjs'

const { Title, Text } = Typography

export default function ChatPage() {
  const { user } = useAuthStore()
  const [threads, setThreads] = useState<ChatThreadSummary[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const loadThreads = () => {
    chatApi.threads().then((t) => {
      setThreads(t)
      if (t.length > 0 && activeId === null) setActiveId(t[0].id)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { loadThreads() }, [])

  useEffect(() => {
    if (activeId !== null) {
      chatApi.messages(activeId).then(setMessages)
    }
  }, [activeId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!draft.trim() || activeId === null) return
    setSending(true)
    try {
      const msg = await chatApi.send(activeId, draft.trim())
      setMessages([...messages, msg])
      setDraft('')
    } finally {
      setSending(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  const activeThread = threads.find((t) => t.id === activeId)

  return (
    <div>
      <Title level={3}>Сообщения</Title>
      {threads.length === 0 ? (
        <Empty description="У вас пока нет диалогов" />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16, height: 560 }}>
          <Card styles={{ body: { padding: 0, overflow: 'auto', height: '100%' } }}>
            <List
              dataSource={threads}
              renderItem={(t) => (
                <List.Item
                  style={{
                    padding: '12px 16px', cursor: 'pointer',
                    background: t.id === activeId ? '#fff7ed' : '#fff',
                  }}
                  onClick={() => setActiveId(t.id)}
                >
                  <List.Item.Meta
                    avatar={<Avatar style={{ background: '#f97316' }}>{t.other_name[0]}</Avatar>}
                    title={
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Text style={{ fontSize: 14 }}>{t.other_name}</Text>
                        {t.unread > 0 && <Badge count={t.unread} size="small" />}
                      </div>
                    }
                    description={<Text type="secondary" ellipsis style={{ fontSize: 12 }}>{t.last_message}</Text>}
                  />
                </List.Item>
              )}
            />
          </Card>

          <Card
            title={activeThread?.other_name}
            styles={{ body: { display: 'flex', flexDirection: 'column', height: 500, padding: 0 } }}
          >
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              {messages.map((m) => {
                const mine = m.sender_id === user?.id
                return (
                  <div key={m.id} style={{ display: 'flex', justifyContent: mine ? 'flex-end' : 'flex-start', marginBottom: 8 }}>
                    <div style={{
                      maxWidth: '70%', padding: '8px 12px', borderRadius: 12,
                      background: mine ? '#f97316' : '#f0f0f0',
                      color: mine ? '#fff' : '#000',
                    }}>
                      <div>{m.text}</div>
                      <div style={{ fontSize: 10, opacity: 0.7, textAlign: 'right' }}>
                        {dayjs(m.created_at).format('HH:mm')}
                      </div>
                    </div>
                  </div>
                )
              })}
              <div ref={bottomRef} />
            </div>
            <div style={{ display: 'flex', gap: 8, padding: 12, borderTop: '1px solid #f0f0f0' }}>
              <Input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onPressEnter={handleSend}
                placeholder="Введите сообщение..."
              />
              <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={handleSend} />
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
