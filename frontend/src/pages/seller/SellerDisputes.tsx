import { useEffect, useState } from 'react'
import { Row, Col, Card, List, Typography, Button, Tag, message, Empty, Space, Popconfirm } from 'antd'
import { disputesApi } from '@/api'
import DisputeThread from '@/components/common/DisputeThread'
import { disputeStatusMeta } from '@/lib/disputeMeta'
import type { Dispute } from '@/types'
import dayjs from 'dayjs'

const { Title, Text } = Typography

export default function SellerDisputes() {
  const [disputes, setDisputes] = useState<Dispute[]>([])
  const [active, setActive] = useState<Dispute | null>(null)

  const load = () => disputesApi.sellerList().then(setDisputes).catch(() => {})
  const openOne = (id: number) => disputesApi.get(id).then(setActive).catch(() => {})
  useEffect(() => { load() }, [])

  const send = async (text: string) => { if (active) { await disputesApi.message(active.id, text); openOne(active.id) } }
  const escalate = async () => { if (active) { await disputesApi.escalate(active.id); await load(); openOne(active.id) } }
  const concede = async () => { if (active) { await disputesApi.concede(active.id); await load(); openOne(active.id); message.success('Возврат оформлен') } }

  return (
    <div>
      <Title level={3}>Споры по заказам</Title>
      <Row gutter={16}>
        <Col xs={24} md={9}>
          <Card styles={{ body: { padding: 0 } }}>
            {disputes.length === 0 ? <Empty description="Споров нет" style={{ padding: 24 }} /> : (
              <List
                dataSource={disputes}
                renderItem={(d) => (
                  <List.Item onClick={() => openOne(d.id)} style={{ cursor: 'pointer', padding: '12px 16px', background: active?.id === d.id ? '#fff7ed' : undefined }}>
                    <List.Item.Meta title={<Text strong>{d.subject}</Text>} description={`Заказ #${d.order_id} · ${dayjs(d.last_message_at).format('DD.MM.YY')}`} />
                    <Tag color={disputeStatusMeta[d.status].color}>{disputeStatusMeta[d.status].label}</Tag>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} md={15}>
          {!active ? <Card><Empty description="Выберите спор" /></Card> : (
            <Card
              title={<Space><span>{active.subject}</span><Tag color={disputeStatusMeta[active.status].color}>{disputeStatusMeta[active.status].label}</Tag></Space>}
              extra={(active.status === 'open' || active.status === 'in_mediation') && (
                <Popconfirm title="Оформить полный возврат покупателю?" onConfirm={concede}>
                  <Button size="small" type="primary">Согласиться на возврат</Button>
                </Popconfirm>
              )}
            >
              {active.reason && <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>Причина: {active.reason}</Text>}
              <DisputeThread dispute={active} myRole="seller" onSend={send} />
            </Card>
          )}
        </Col>
      </Row>
    </div>
  )
}
