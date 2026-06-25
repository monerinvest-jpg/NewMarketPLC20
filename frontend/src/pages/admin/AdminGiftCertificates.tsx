import { useEffect, useState } from 'react'
import { Card, Table, Typography, Button, InputNumber, Form, message, Tag, Space, Modal, Input } from 'antd'
import { giftsApi } from '@/api'
import type { GiftCertificate } from '@/types'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography

const statusMeta: Record<string, { color: string; label: string }> = {
  active: { color: 'green', label: 'Активен' },
  redeemed: { color: 'blue', label: 'Использован' },
  cancelled: { color: 'default', label: 'Отменён' },
  expired: { color: 'default', label: 'Истёк' },
}

export default function AdminGiftCertificates() {
  const [list, setList] = useState<GiftCertificate[]>([])
  const [open, setOpen] = useState(false)
  const [issued, setIssued] = useState<GiftCertificate[] | null>(null)
  const [form] = Form.useForm()

  const load = () => giftsApi.adminList().then(setList).catch(() => {})
  useEffect(() => { load() }, [])

  const issue = async () => {
    const v = await form.validateFields()
    const certs = await giftsApi.adminIssue(v)
    setIssued(certs); setOpen(false); form.resetFields(); load()
    message.success(`Выпущено сертификатов: ${certs.length}`)
  }

  return (
    <div>
      <Title level={3}>Подарочные сертификаты</Title>
      <Paragraph type="secondary">Выпускайте промо-сертификаты для кампаний. Активация начисляется на промо-баланс покупателя.</Paragraph>

      <Card extra={<Button type="primary" onClick={() => setOpen(true)}>Выпустить</Button>}>
        <Table<GiftCertificate>
          dataSource={list} rowKey="id" pagination={{ pageSize: 20 }} size="small"
          columns={[
            { title: 'Код', dataIndex: 'code', render: (v) => <Text code>{v}</Text> },
            { title: 'Сумма', dataIndex: 'amount', render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
            { title: 'Статус', dataIndex: 'status', render: (v) => <Tag color={statusMeta[v]?.color}>{statusMeta[v]?.label}</Tag> },
            { title: 'Сообщение', dataIndex: 'message', render: (v) => v || '—' },
            { title: 'Создан', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YY') },
          ]}
        />
      </Card>

      <Modal title="Выпустить сертификаты" open={open} onCancel={() => setOpen(false)} onOk={issue} okText="Выпустить">
        <Form form={form} layout="vertical" initialValues={{ count: 1 }}>
          <Form.Item name="amount" label="Номинал, ₽" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="count" label="Количество" rules={[{ required: true }]}>
            <InputNumber min={1} max={500} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="message" label="Сообщение (необязательно)">
            <Input.TextArea rows={2} placeholder="Промо-кампания" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="Сертификаты выпущены" open={!!issued} onCancel={() => setIssued(null)} footer={<Button type="primary" onClick={() => setIssued(null)}>Готово</Button>}>
        <Space direction="vertical" style={{ width: '100%' }}>
          {issued?.map((c) => <Text key={c.id} code copyable>{c.code}</Text>)}
        </Space>
      </Modal>
    </div>
  )
}
