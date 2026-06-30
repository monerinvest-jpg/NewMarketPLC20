import { useEffect, useState } from 'react'
import {
  Typography, Card, Row, Col, Progress, Button, Spin, Empty, Tag, Collapse, message,
} from 'antd'
import { ReadOutlined, CheckCircleFilled, PlayCircleOutlined, LinkOutlined } from '@ant-design/icons'
import { academyApi } from '@/api'

const { Title, Paragraph, Text } = Typography

const levelTag: Record<string, { label: string; color: string }> = {
  beginner: { label: 'Начальный', color: 'green' },
  intermediate: { label: 'Средний', color: 'blue' },
  advanced: { label: 'Продвинутый', color: 'volcano' },
}

export default function SellerAcademy() {
  const [courses, setCourses] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [openCourse, setOpenCourse] = useState<any>(null)

  const loadCourses = () => { setLoading(true); academyApi.courses().then(setCourses).finally(() => setLoading(false)) }
  useEffect(() => { loadCourses() }, [])

  const openCourseView = async (id: number) => setOpenCourse(await academyApi.course(id))

  const complete = async (lessonId: number) => {
    try {
      await academyApi.completeLesson(lessonId)
      message.success('Урок отмечен пройденным')
      const fresh = await academyApi.course(openCourse.id)
      setOpenCourse(fresh)
    } catch { message.error('Ошибка') }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  // ── Course detail view ──
  if (openCourse) {
    const done = openCourse.lessons.filter((l: any) => l.completed).length
    return (
      <div style={{ maxWidth: 820, margin: '0 auto' }}>
        <Button onClick={() => { setOpenCourse(null); loadCourses() }} style={{ marginBottom: 12 }}>← К списку</Button>
        <Title level={3} style={{ marginTop: 0 }}>{openCourse.title}</Title>
        <Paragraph type="secondary">{openCourse.description}</Paragraph>
        <Progress percent={openCourse.lessons.length ? Math.round(done / openCourse.lessons.length * 100) : 0} style={{ marginBottom: 16 }} />
        <Collapse
          items={openCourse.lessons.map((l: any) => ({
            key: String(l.id),
            label: (
              <span>
                {l.completed && <CheckCircleFilled style={{ color: '#4d7c0f', marginRight: 8 }} />}
                {l.content_type === 'video' ? <PlayCircleOutlined style={{ marginRight: 6 }} /> : l.content_type === 'link' ? <LinkOutlined style={{ marginRight: 6 }} /> : <ReadOutlined style={{ marginRight: 6 }} />}
                {l.title}
              </span>
            ),
            children: (
              <div>
                {l.content_type === 'video' && l.video_url && (
                  <video src={l.video_url} controls style={{ width: '100%', maxHeight: 380, borderRadius: 8, background: '#000', marginBottom: 12 }} />
                )}
                {l.content_type === 'link' && l.video_url && (
                  <Paragraph><a href={l.video_url} target="_blank" rel="noreferrer">Открыть материал →</a></Paragraph>
                )}
                {l.body && <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{l.body}</Paragraph>}
                {!l.completed && <Button type="primary" onClick={() => complete(l.id)}>Отметить пройденным</Button>}
              </div>
            ),
          }))}
        />
      </div>
    )
  }

  // ── Course list ──
  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <Title level={3}>Академия продавца</Title>
      <Paragraph type="secondary">
        Бесплатные курсы от площадки: как продавать больше, оформлять карточки, работать с доставкой и продвижением.
      </Paragraph>
      {courses.length === 0 ? (
        <Empty description="Курсы скоро появятся" />
      ) : (
        <Row gutter={[16, 16]}>
          {courses.map((c) => (
            <Col xs={24} sm={12} md={8} key={c.id}>
              <Card
                hoverable
                onClick={() => openCourseView(c.id)}
                cover={c.cover_url ? <img src={c.cover_url} alt={c.title} style={{ height: 140, objectFit: 'cover' }} /> : undefined}
              >
                <Tag color={levelTag[c.level]?.color}>{levelTag[c.level]?.label || c.level}</Tag>
                <Title level={5} style={{ marginTop: 8 }}>{c.title}</Title>
                <Text type="secondary" style={{ fontSize: 13 }}>{c.lesson_count} уроков</Text>
                <Progress percent={c.progress_percent} size="small" style={{ marginTop: 8 }} />
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  )
}
