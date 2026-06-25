import { useEffect, useState } from 'react'
import {
  Row, Col, Card, Typography, Input, Button, InputNumber, Form, message, Table, Tag, Statistic, Divider, Modal,
} from 'antd'
import { GiftOutlined } from '@ant-design/icons'
import { giftsApi } from '@/api'
import type { PromoOverview } from '@/types'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography

const statusMeta: Record<string, { color: string; label: string }> = {
  active: { color: 'green', label: 'Активен' },
  redeemed: { color: 'blue', label: 'Использован' },
  cancelled: { color: 'default', label: 'Отменён' },
  expired: { color: 'default', label: 'Истёк' },
}

export default function GiftCertificatesPage() {
  const [data, setData] = useState<PromoOverview | null>(null)
  const [code, setCode] = useState('')
  const [buyOpen, setBuyOpen] = useState(false)
  const [issued, setIssued] = useState<string | null>(null)
  const [form] = Form.useForm()

  const load = () => giftsApi.promoBalance().then(setData).catch(() => {})
  useEffect(() => { load() }, [])

  const redeem = async () => {
    if (!code.trim()) return
    try {
      const r = await giftsApi.redeem(code.trim())
      message.success(`Начислено ${Number(r.credited).toLocaleString('ru')} ₽ на промо-баланс`)
      setCode(''); load()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Не удалось активировать')
    }
  }

  const buy = async () => {
    const v = await form.validateFields()
    try {
      const cert = await giftsApi.purchase(v)
      setIssued(cert.code); setBuyOpen(false); form.resetFields(); load()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Не удалось купить')
    }
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: 24 }}>
      <Title level={3}><GiftOutlined /> Сертификаты и промо-баланс</Title>

      <Row gutter={16}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Промо-баланс" value={`${Number(data?.promo_balance || 0).toLocaleString('ru')} ₽`} valueStyle={{ color: '#f97316' }} />
            <Paragraph type="secondary" style={{ marginTop: 8, fontSize: 12 }}>
              Промо-баланс автоматически списывается при оформлении заказа.
            </Paragraph>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="Активировать сертификат">
            <Input placeholder="GIFT-XXXX-XXXX" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} onPressEnter={redeem} />
            <Button type="primary" block style={{ marginTop: 12 }} onClick={redeem}>Активировать</Button>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="Купить сертификат">
            <Paragraph type="secondary" style={{ fontSize: 12 }}>Оплата с основного баланса. Код можно подарить.</Paragraph>
            <Button type="primary" block icon={<GiftOutlined />} onClick={() => setBuyOpen(true)}>Купить в подарок</Button>
          </Card>
        </Col>
      </Row>

      <Divider />
      <Title level={5}>Мои сертификаты</Title>
      <Table
        dataSource={data?.purchased || []} rowKey="id" pagination={false} size="small" style={{ marginBottom: 24 }}
        locale={{ emptyText: 'Вы не покупали сертификатов' }}
        columns={[
          { title: 'Код', dataIndex: 'code', render: (v) => <Text code>{v}</Text> },
          { title: 'Сумма', dataIndex: 'amount', render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
          { title: 'Получатель', dataIndex: 'recipient_email', render: (v) => v || '—' },
          { title: 'Статус', dataIndex: 'status', render: (v) => <Tag color={statusMeta[v]?.color}>{statusMeta[v]?.label}</Tag> },
          { title: 'Создан', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YY') },
        ]}
      />

      <Title level={5}>История промо-баланса</Title>
      <Table
        dataSource={data?.transactions || []} rowKey="id" pagination={{ pageSize: 8 }} size="small"
        locale={{ emptyText: 'Операций пока нет' }}
        columns={[
          { title: 'Операция', dataIndex: 'description' },
          { title: 'Сумма', dataIndex: 'change', width: 120, render: (v) => <Text type={Number(v) < 0 ? 'danger' : 'success'}>{Number(v) > 0 ? '+' : ''}{Number(v).toLocaleString('ru')} ₽</Text> },
          { title: 'Остаток', dataIndex: 'balance_after', width: 120, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
          { title: 'Дата', dataIndex: 'created_at', width: 140, render: (v) => dayjs(v).format('DD.MM.YY HH:mm') },
        ]}
      />

      <Modal title="Купить подарочный сертификат" open={buyOpen} onCancel={() => setBuyOpen(false)} onOk={buy} okText="Купить">
        <Form form={form} layout="vertical">
          <Form.Item name="amount" label="Сумма, ₽" rules={[{ required: true, message: 'Укажите сумму' }]}>
            <InputNumber min={100} step={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="recipient_email" label="Email получателя (необязательно)">
            <Input type="email" placeholder="friend@example.com" />
          </Form.Item>
          <Form.Item name="message" label="Сообщение (необязательно)">
            <Input.TextArea rows={2} placeholder="С праздником!" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="Сертификат куплен!" open={!!issued} onCancel={() => setIssued(null)} footer={<Button type="primary" onClick={() => setIssued(null)}>Готово</Button>}>
        <Paragraph>Передайте этот код получателю — он активирует его в этом разделе:</Paragraph>
        <Title level={3} copyable style={{ textAlign: 'center' }}>{issued}</Title>
      </Modal>
    </div>
  )
}
