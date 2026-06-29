import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Layout, Menu, Typography, Progress, Button, Spin, Tag, message, Result, Space,
} from 'antd'
import {
  LockOutlined, CheckCircleTwoTone, PlayCircleOutlined, FilePdfOutlined,
  FileTextOutlined, CheckOutlined,
} from '@ant-design/icons'
import { coursesApi } from '@/api'
import { useAuthStore } from '@/store/authStore'
import type { CourseDetail, CourseLessonNode } from '@/types'

const { Sider, Content } = Layout
const { Title, Text, Paragraph } = Typography

const typeIcon: Record<string, JSX.Element> = {
  video: <PlayCircleOutlined />,
  pdf: <FilePdfOutlined />,
  text: <FileTextOutlined />,
}

/** Repeated diagonal watermark with the buyer's identity — traces leaks. */
function Watermark({ label }: { label: string }) {
  return (
    <div
      style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden',
        display: 'flex', flexWrap: 'wrap', alignContent: 'space-around',
        justifyContent: 'space-around', opacity: 0.12, zIndex: 5,
      }}
    >
      {Array.from({ length: 24 }).map((_, i) => (
        <span key={i} style={{ transform: 'rotate(-30deg)', fontSize: 14, color: '#000', whiteSpace: 'nowrap' }}>
          {label}
        </span>
      ))}
    </div>
  )
}

export default function CoursePlayerPage() {
  const { productId } = useParams()
  const pid = Number(productId)
  const user = useAuthStore((s) => s.user)
  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState<CourseLessonNode | null>(null)
  const [mediaUrl, setMediaUrl] = useState<string | null>(null)
  const [mediaLoading, setMediaLoading] = useState(false)
  const urlRef = useRef<string | null>(null)

  const watermark = user?.email || 'protected'

  const load = async () => {
    try {
      const c = await coursesApi.get(pid)
      setCourse(c)
      // auto-select first accessible lesson
      const first = c.modules.flatMap((m) => m.lessons).find((l) => !l.locked)
      if (first) selectLesson(first)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [pid])
  useEffect(() => () => { if (urlRef.current) URL.revokeObjectURL(urlRef.current) }, [])

  const revoke = () => {
    if (urlRef.current) { URL.revokeObjectURL(urlRef.current); urlRef.current = null }
  }

  const selectLesson = async (lesson: CourseLessonNode) => {
    setActive(lesson)
    revoke()
    setMediaUrl(null)
    if (lesson.locked) return
    if (lesson.lesson_type === 'text') return  // text_body already in node
    setMediaLoading(true)
    try {
      const resp = await coursesApi.lessonContent(pid, lesson.id)
      const url = URL.createObjectURL(resp.data)
      urlRef.current = url
      setMediaUrl(url)
    } catch {
      message.error('Не удалось загрузить материал')
    } finally {
      setMediaLoading(false)
    }
  }

  const markComplete = async () => {
    if (!active) return
    try {
      const r = await coursesApi.completeLesson(pid, active.id)
      message.success('Урок отмечен пройденным')
      setCourse((c) => {
        if (!c) return c
        const modules = c.modules.map((m) => ({
          ...m,
          lessons: m.lessons.map((l) => (l.id === active.id ? { ...l, completed: true } : l)),
        }))
        return { ...c, modules, progress_percent: r.progress_percent }
      })
      setActive((l) => (l ? { ...l, completed: true } : l))
    } catch {
      message.error('Ошибка')
    }
  }

  if (loading) return <div className="flex justify-center py-20"><Spin size="large" /></div>
  if (!course) return <Result status="404" title="Курс не найден" />

  const menuItems = course.modules.map((m) => ({
    key: `m-${m.id}`,
    label: m.title,
    type: 'group' as const,
    children: m.lessons.map((l) => ({
      key: String(l.id),
      icon: l.locked ? <LockOutlined /> : l.completed ? <CheckCircleTwoTone twoToneColor="#52c41a" /> : typeIcon[l.lesson_type],
      label: (
        <span>
          {l.title}{' '}
          {l.is_preview && <Tag color="green">превью</Tag>}
        </span>
      ),
    })),
  }))

  return (
    <Layout style={{ background: '#fff', minHeight: '70vh' }}>
      <Sider width={320} theme="light" style={{ borderRight: '1px solid #f0f0f0', padding: '16px 0' }}>
        <div style={{ padding: '0 16px 12px' }}>
          <Title level={5} style={{ marginBottom: 4 }}>{course.title}</Title>
          {!course.enrolled && (
            <Link to={`/products/${pid}`}><Button size="small" type="primary" block>Купить курс</Button></Link>
          )}
          <Progress percent={course.progress_percent} size="small" style={{ marginTop: 8 }} />
          <Text type="secondary">{course.completed_lessons} из {course.total_lessons} уроков</Text>
        </div>
        <Menu
          mode="inline"
          selectedKeys={active ? [String(active.id)] : []}
          items={menuItems}
          onClick={({ key }) => {
            const lesson = course.modules.flatMap((m) => m.lessons).find((l) => String(l.id) === key)
            if (lesson) selectLesson(lesson)
          }}
        />
      </Sider>

      <Content style={{ padding: 24 }} onContextMenu={(e) => e.preventDefault()}>
        {!active ? (
          <Text type="secondary">Выберите урок слева.</Text>
        ) : active.locked ? (
          <Result
            icon={<LockOutlined />}
            title="Урок доступен после покупки курса"
            extra={<Link to={`/products/${pid}`}><Button type="primary">Купить курс</Button></Link>}
          />
        ) : (
          <div>
            <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
              <Title level={4} style={{ margin: 0 }}>{active.title}</Title>
              {course.enrolled && (
                <Button
                  icon={<CheckOutlined />}
                  type={active.completed ? 'default' : 'primary'}
                  disabled={active.completed}
                  onClick={markComplete}
                >
                  {active.completed ? 'Пройдено' : 'Отметить пройденным'}
                </Button>
              )}
            </Space>

            {mediaLoading && <div className="flex justify-center py-12"><Spin /></div>}

            {/* TEXT */}
            {active.lesson_type === 'text' && (
              <div style={{ position: 'relative' }}>
                <Watermark label={watermark} />
                <div
                  style={{ userSelect: 'none', position: 'relative', zIndex: 1 }}
                  dangerouslySetInnerHTML={{ __html: active.text_body || '<p>Пусто.</p>' }}
                />
              </div>
            )}

            {/* VIDEO */}
            {active.lesson_type === 'video' && mediaUrl && (
              <div style={{ position: 'relative', maxWidth: 900 }}>
                <Watermark label={watermark} />
                <video
                  src={mediaUrl}
                  controls
                  controlsList="nodownload noplaybackrate"
                  disablePictureInPicture
                  onContextMenu={(e) => e.preventDefault()}
                  style={{ width: '100%', borderRadius: 8, position: 'relative', zIndex: 1 }}
                />
              </div>
            )}

            {/* PDF */}
            {active.lesson_type === 'pdf' && mediaUrl && (
              <div style={{ position: 'relative', height: '80vh' }}>
                <Watermark label={watermark} />
                <iframe
                  title={active.title}
                  src={`${mediaUrl}#toolbar=0`}
                  style={{ width: '100%', height: '100%', border: 'none', position: 'relative', zIndex: 1 }}
                />
              </div>
            )}

            {!mediaLoading && !mediaUrl && active.lesson_type !== 'text' && (
              <Paragraph type="secondary">Материал ещё не загружен продавцом.</Paragraph>
            )}
          </div>
        )}
      </Content>
    </Layout>
  )
}
