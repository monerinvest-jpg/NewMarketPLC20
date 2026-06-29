import { useEffect, useState } from 'react'
import {
  Typography, Card, Tag, Button, Upload, message, Spin, Row, Col,
  Alert, Space, Progress,
} from 'antd'
import { UploadOutlined, SafetyCertificateOutlined, CrownOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { shopsApi } from '@/api'

const { Title, Paragraph, Text } = Typography

const badgeView: Record<string, { label: string; color: string; icon: any }> = {
  vip: { label: 'VIP-магазин', color: 'gold', icon: <CrownOutlined /> },
  verified: { label: 'Проверенный', color: 'green', icon: <SafetyCertificateOutlined /> },
}

export default function SellerTrust() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [files, setFiles] = useState<UploadFile[]>([])
  const [busy, setBusy] = useState(false)

  const load = () => {
    setLoading(true)
    shopsApi.getTrust().then(setData).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const submitKyc = async () => {
    const raw = files.map((f) => f.originFileObj).filter(Boolean) as File[]
    if (!raw.length) { message.error('Прикрепите документы'); return }
    setBusy(true)
    try {
      await shopsApi.submitKyc(raw)
      message.success('Документы отправлены на проверку')
      setFiles([]); load()
    } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
    finally { setBusy(false) }
  }

  const buyVip = async () => {
    setBusy(true)
    try {
      await shopsApi.buyVip()
      message.success('VIP-статус активирован')
      load()
    } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
    finally { setBusy(false) }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!data) return null

  const badge = data.badge ? badgeView[data.badge] : null
  const kycStatus = data.kyc?.status
  const repProgress = Math.min(100, Math.round((parseFloat(data.rating) / parseFloat(data.vip_auto_rating_min)) * 100))
  const reviewsProgress = Math.min(100, Math.round((data.reviews_count / data.vip_auto_reviews_min) * 100))

  return (
    <div style={{ maxWidth: 820, margin: '0 auto' }}>
      <Title level={3}>Доверие и статус магазина</Title>
      <Paragraph type="secondary">
        Подтверждайте надёжность магазина: пройдите верификацию документов и получите бейджи доверия —
        они повышают конверсию и видны покупателям.
      </Paragraph>

      <Card style={{ marginBottom: 16 }}>
        <Space size="large" align="center">
          <Text strong>Текущий бейдж:</Text>
          {badge ? <Tag color={badge.color} icon={badge.icon} style={{ fontSize: 14, padding: '4px 10px' }}>{badge.label}</Tag>
                 : <Tag>нет</Tag>}
        </Space>
      </Card>

      <Card title={<span><SafetyCertificateOutlined /> Верификация (KYC)</span>} style={{ marginBottom: 16 }}>
        {kycStatus === 'verified' ? (
          <Alert type="success" showIcon message="Магазин верифицирован — бейдж «Проверенный» активен." />
        ) : kycStatus === 'pending' ? (
          <Alert type="info" showIcon message="Документы на проверке. Мы уведомим вас о решении." />
        ) : (
          <>
            {kycStatus === 'rejected' && (
              <Alert type="error" showIcon style={{ marginBottom: 12 }}
                message="Заявка отклонена" description={data.kyc?.reason} />
            )}
            <Paragraph type="secondary">
              Загрузите документы (паспорт/ИНН/ОГРН/выписку). Файлы хранятся приватно и видны только модератору.
            </Paragraph>
            <Upload
              multiple beforeUpload={() => false}
              fileList={files} onChange={({ fileList }) => setFiles(fileList)}
            >
              <Button icon={<UploadOutlined />}>Выбрать файлы</Button>
            </Upload>
            <Button type="primary" style={{ marginTop: 12 }} loading={busy} onClick={submitKyc} disabled={!files.length}>
              Отправить на проверку
            </Button>
          </>
        )}
      </Card>

      <Card title={<span><CrownOutlined /> VIP-статус</span>}>
        <Row gutter={16} align="middle">
          <Col xs={24} md={12}>
            <Paragraph>
              VIP можно <b>купить</b> за <b>{data.vip_price} ₽</b> на {data.vip_days} дней,
              либо <b>заработать репутацией</b>: рейтинг ≥ {data.vip_auto_rating_min} и ≥ {data.vip_auto_reviews_min} отзывов.
            </Paragraph>
            {data.vip_until && <Alert type="success" showIcon message={`VIP активен до ${new Date(data.vip_until).toLocaleDateString('ru')}`} style={{ marginBottom: 12 }} />}
            <Button type="primary" loading={busy} onClick={buyVip} icon={<CrownOutlined />}>
              Купить VIP за {data.vip_price} ₽
            </Button>
          </Col>
          <Col xs={24} md={12}>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary">Рейтинг ({data.rating} / {data.vip_auto_rating_min})</Text>
              <Progress percent={repProgress} strokeColor="#b45309" />
            </div>
            <div>
              <Text type="secondary">Отзывы ({data.reviews_count} / {data.vip_auto_reviews_min})</Text>
              <Progress percent={reviewsProgress} strokeColor="#4d7c0f" />
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  )
}
