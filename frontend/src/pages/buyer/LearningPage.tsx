import { useEffect, useState } from 'react'
import { Card, Progress, Typography, Empty, Spin, Button, Row, Col } from 'antd'
import { ReadOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { learningApi } from '@/api'
import type { MyCourse } from '@/types'

const { Title, Text } = Typography

export default function LearningPage() {
  const [courses, setCourses] = useState<MyCourse[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    learningApi.myCourses()
      .then(setCourses)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex justify-center py-20"><Spin size="large" /></div>

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <Title level={3}><ReadOutlined className="mr-2" />Обучение</Title>
      <Text type="secondary">Ваши курсы. Продолжайте с того места, где остановились.</Text>

      {courses.length === 0 ? (
        <Empty className="mt-12" description="У вас пока нет курсов">
          <Button type="primary" onClick={() => navigate('/catalog?type=course')}>Найти курсы</Button>
        </Empty>
      ) : (
        <Row gutter={[16, 16]} className="mt-6">
          {courses.map((c) => (
            <Col xs={24} sm={12} lg={8} key={c.product_id}>
              <Card
                hoverable
                onClick={() => navigate(`/learn/${c.product_id}`)}
                actions={[
                  <Button type="link" icon={<PlayCircleOutlined />} key="go">
                    {c.progress_percent > 0 ? 'Продолжить' : 'Начать'}
                  </Button>,
                ]}
              >
                <Card.Meta
                  title={c.title}
                  description={<Progress percent={c.progress_percent} size="small" />}
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  )
}
