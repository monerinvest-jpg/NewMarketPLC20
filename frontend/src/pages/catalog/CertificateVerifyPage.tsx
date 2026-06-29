import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Result, Spin, Descriptions, Typography } from 'antd'
import { SafetyCertificateOutlined } from '@ant-design/icons'
import { coursesApi } from '@/api'
import type { Certificate } from '@/types'

const { Title } = Typography

export default function CertificateVerifyPage() {
  const { code } = useParams()
  const [cert, setCert] = useState<Certificate | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!code) return
    coursesApi.verifyCertificate(code)
      .then(setCert)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [code])

  if (loading) return <div className="flex justify-center py-20"><Spin size="large" /></div>

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <Title level={3}><SafetyCertificateOutlined className="mr-2" />Проверка сертификата</Title>
      {notFound || !cert ? (
        <Result status="error" title="Сертификат не найден" subTitle={`Код: ${code}`} />
      ) : (
        <Card>
          <Result status="success" title="Сертификат подлинный" />
          <Descriptions column={1} bordered>
            <Descriptions.Item label="Выдан">{cert.recipient_name}</Descriptions.Item>
            <Descriptions.Item label="Курс">{cert.course_title}</Descriptions.Item>
            <Descriptions.Item label="Дата">{new Date(cert.issued_at).toLocaleDateString('ru')}</Descriptions.Item>
            <Descriptions.Item label="Код">{cert.code}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </div>
  )
}
