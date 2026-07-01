import { Typography, Input, Button } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import { useState } from 'react'
import type { Dispute } from '@/types'
import dayjs from 'dayjs'

const { Text } = Typography
const { TextArea } = Input

const roleLabel: Record<string, string> = {
  buyer: 'Покупатель', seller: 'Продавец', mediator: 'Арбитр', system: 'Система',
}

/** Renders the dispute conversation plus a reply box (hidden when closed). */
export default function DisputeThread({
  dispute, myRole, onSend,
}: { dispute: Dispute; myRole: 'buyer' | 'seller' | 'mediator'; onSend: (text: string) => Promise<void> }) {
  const [text, setText] = useState('')
  const closed = dispute.status === 'resolved' || dispute.status === 'cancelled'

  const send = async () => {
    if (!text.trim()) return
    await onSend(text.trim())
    setText('')
  }

  const mine = (role: string) =>
    (myRole === 'buyer' && role === 'buyer') ||
    (myRole === 'seller' && role === 'seller') ||
    (myRole === 'mediator' && role === 'mediator')

  return (
    <div>
      <div style={{ maxHeight: 360, overflowY: 'auto', marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {dispute.messages?.map((m) => (
          m.sender_role === 'system' ? (
            <div key={m.id} style={{ textAlign: 'center' }}>
              <Text type="secondary" style={{ fontSize: 12, fontStyle: 'italic' }}>{m.text}</Text>
            </div>
          ) : (
            <div key={m.id} style={{ alignSelf: mine(m.sender_role) ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
              <div style={{ padding: '8px 12px', borderRadius: 12, background: mine(m.sender_role) ? '#b45309' : '#f1f5f9', color: mine(m.sender_role) ? '#fff' : '#0f172a' }}>
                {m.text}
              </div>
              <Text type="secondary" style={{ fontSize: 11 }}>{roleLabel[m.sender_role] || m.sender_role} · {dayjs(m.created_at).format('DD.MM HH:mm')}</Text>
            </div>
          )
        ))}
      </div>
      {!closed && (
        <div style={{ display: 'flex', gap: 8 }}>
          <TextArea rows={2} value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Сообщение…" onPressEnter={(e) => { e.preventDefault(); send() }} />
          <Button type="primary" icon={<SendOutlined />} onClick={send} />
        </div>
      )}
    </div>
  )
}
