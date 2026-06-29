import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Layout, Menu, Typography, Progress, Button, Spin, Tag, message, Result, Space, Radio, Alert,
  Modal, Input,
} from 'antd'
import {
  LockOutlined, CheckCircleTwoTone, PlayCircleOutlined, FilePdfOutlined,
  FileTextOutlined, CheckOutlined, QuestionCircleOutlined, TrophyOutlined,
} from '@ant-design/icons'
import Hls from 'hls.js'
import { coursesApi } from '@/api'
import { useAuthStore } from '@/store/authStore'
import type { CourseDetail, CourseLessonNode, QuizResult } from '@/types'

const { Sider, Content } = Layout
const { Title, Text, Paragraph } = Typography

const typeIcon: Record<string, JSX.Element> = {
  video: <PlayCircleOutlined />,
  pdf: <FilePdfOutlined />,
  text: <FileTextOutlined />,
  quiz: <QuestionCircleOutlined />,
}

/** Repeated diagonal watermark with the buyer's identity — traces leaks. */
function Watermark({ label }: { label: string }) {
  return (
    <div style={{
      position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden',
      display: 'flex', flexWrap: 'wrap', alignContent: 'space-around',
      justifyContent: 'space-around', opacity: 0.12, zIndex: 5,
    }}>
      {Array.from({ length: 24 }).map((_, i) => (
        <span key={i} style={{ transform: 'rotate(-30deg)', fontSize: 14, color: '#000', whiteSpace: 'nowrap' }}>{label}</span>
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
  const [quizAnswers, setQuizAnswers] = useState<number[]>([])
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null)
  const [certModal, setCertModal] = useState(false)
  const [certName, setCertName] = useState('')
  const blobRef = useRef<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const hlsRef = useRef<Hls | null>(null)

  const watermark = user?.email || 'protected'

  const load = async () => {
    try {
      const c = await coursesApi.get(pid)
      setCourse(c)
      const first = c.modules.flatMap((m) => m.lessons).find((l) => !l.locked)
      if (first) selectLesson(first)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [pid])
  useEffect(() => () => { cleanup() }, [])

  const cleanup = () => {
    if (blobRef.current) { URL.revokeObjectURL(blobRef.current); blobRef.current = null }
    if (hlsRef.current) { hlsRef.current.destroy(); hlsRef.current = null }
  }

  const selectLesson = async (lesson: CourseLessonNode) => {
    cleanup()
    setMediaUrl(null)
    setQuizResult(null)
    setQuizAnswers(new Array(lesson.quiz?.questions.length || 0).fill(-1))
    setActive(lesson)
    if (lesson.locked) return
    // Blob fetch only for PDF and non-HLS video; HLS video uses hls.js, text/quiz are inline.
    const needsBlob = lesson.lesson_type === 'pdf' || (lesson.lesson_type === 'video' && !lesson.hls_ready)
    if (!needsBlob) return
    setMediaLoading(true)
    try {
      const resp = await coursesApi.lessonContent(pid, lesson.id)
      const url = URL.createObjectURL(resp.data)
      blobRef.current = url
      setMediaUrl(url)
    } catch {
      message.error('Не удалось загрузить материал')
    } finally {
      setMediaLoading(false)
    }
  }

  // Encrypted-HLS playback via hls.js, attaching the Bearer token to every
  // request (playlist, segments, and the AES key are all entitlement-gated).
  useEffect(() => {
    if (!active || active.locked || active.lesson_type !== 'video' || !active.hls_ready) return
    const videoEl = videoRef.current
    if (!videoEl) return
    const token = localStorage.getItem('access_token')
    const src = coursesApi.hlsPlaylistUrl(pid, active.id)
    if (Hls.isSupported()) {
      const hls = new Hls({
        xhrSetup: (xhr) => { if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`) },
      })
      hlsRef.current = hls
      hls.loadSource(src)
      hls.attachMedia(videoEl)
      return () => { hls.destroy(); hlsRef.current = null }
    }
  }, [active, pid])

  const markComplete = async () => {
    if (!active) return
    try {
      const r = await coursesApi.completeLesson(pid, active.id)
      applyCompletion(active.id, r.progress_percent)
      message.success('Урок отмечен пройденным')
    } catch { message.error('Ошибка') }
  }

  const applyCompletion = (lessonId: number, pct: number) => {
    setCourse((c) => c && ({
      ...c,
      progress_percent: pct,
      completed_lessons: c.modules.flatMap((m) => m.lessons).filter((l) => l.completed || l.id === lessonId).length,
      modules: c.modules.map((m) => ({ ...m, lessons: m.lessons.map((l) => (l.id === lessonId ? { ...l, completed: true } : l)) })),
    }))
    setActive((l) => (l ? { ...l, completed: true } : l))
  }

  const submitQuiz = async () => {
    if (!active) return
    try {
      const r = await coursesApi.submitQuiz(pid, active.id, quizAnswers)
      setQuizResult(r)
      if (r.passed) applyCompletion(active.id, (await coursesApi.get(pid)).progress_percent)
    } catch { message.error('Ошибка отправки') }
  }

  const openCertModal = () => {
    setCertName(user?.full_name || '')
    setCertModal(true)
  }

  const confirmCertificate = async () => {
    const name = certName.trim()
    if (!name) { message.error('Укажите ФИО'); return }
    try {
      await coursesApi.issueCertificate(pid, name)            // set the recipient name (ФИО)
      const resp = await coursesApi.certificatePdf(pid)        // then render the PDF
      const url = URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url; a.download = `certificate-${pid}.pdf`; a.click()
      URL.revokeObjectURL(url)
      setCertModal(false)
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Сертификат недоступен')
    }
  }

  if (loading) return <div className="flex justify-center py-20"><Spin size="large" /></div>
  if (!course) return <Result status="404" title="Курс не найден" />

  const menuItems = course.modules.map((m) => ({
    key: `m-${m.id}`, label: m.title, type: 'group' as const,
    children: m.lessons.map((l) => ({
      key: String(l.id),
      icon: l.locked ? <LockOutlined /> : l.completed ? <CheckCircleTwoTone twoToneColor="#52c41a" /> : typeIcon[l.lesson_type],
      label: <span>{l.title} {l.is_preview && <Tag color="green">превью</Tag>}</span>,
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
          {course.enrolled && course.progress_percent >= 100 && (
            <Button block type="primary" icon={<TrophyOutlined />} style={{ marginTop: 8 }} onClick={openCertModal}>
              Сертификат
            </Button>
          )}
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
          <Result icon={<LockOutlined />} title="Урок доступен после покупки курса"
            extra={<Link to={`/products/${pid}`}><Button type="primary">Купить курс</Button></Link>} />
        ) : (
          <div>
            <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
              <Title level={4} style={{ margin: 0 }}>{active.title}</Title>
              {course.enrolled && active.lesson_type !== 'quiz' && (
                <Button icon={<CheckOutlined />} type={active.completed ? 'default' : 'primary'}
                  disabled={active.completed} onClick={markComplete}>
                  {active.completed ? 'Пройдено' : 'Отметить пройденным'}
                </Button>
              )}
            </Space>

            {mediaLoading && <div className="flex justify-center py-12"><Spin /></div>}

            {/* TEXT */}
            {active.lesson_type === 'text' && (
              <div style={{ position: 'relative' }}>
                <Watermark label={watermark} />
                <div style={{ userSelect: 'none', position: 'relative', zIndex: 1 }}
                  dangerouslySetInnerHTML={{ __html: active.text_body || '<p>Пусто.</p>' }} />
              </div>
            )}

            {/* VIDEO (HLS encrypted, or blob fallback) */}
            {active.lesson_type === 'video' && active.hls_ready && (
              <div style={{ position: 'relative', maxWidth: 900 }}>
                <Watermark label={watermark} />
                <video ref={videoRef} controls controlsList="nodownload noplaybackrate"
                  disablePictureInPicture onContextMenu={(e) => e.preventDefault()}
                  style={{ width: '100%', borderRadius: 8, position: 'relative', zIndex: 1 }} />
              </div>
            )}
            {active.lesson_type === 'video' && !active.hls_ready && mediaUrl && (
              <div style={{ position: 'relative', maxWidth: 900 }}>
                <Watermark label={watermark} />
                <video src={mediaUrl} controls controlsList="nodownload noplaybackrate"
                  disablePictureInPicture onContextMenu={(e) => e.preventDefault()}
                  style={{ width: '100%', borderRadius: 8, position: 'relative', zIndex: 1 }} />
                <Alert type="info" showIcon style={{ marginTop: 8 }}
                  message="Видео обрабатывается в защищённый формат — обновите страницу через минуту." />
              </div>
            )}

            {/* PDF */}
            {active.lesson_type === 'pdf' && mediaUrl && (
              <div style={{ position: 'relative', height: '80vh' }}>
                <Watermark label={watermark} />
                <iframe title={active.title} src={`${mediaUrl}#toolbar=0`}
                  style={{ width: '100%', height: '100%', border: 'none', position: 'relative', zIndex: 1 }} />
              </div>
            )}

            {/* QUIZ */}
            {active.lesson_type === 'quiz' && active.quiz && (
              <div style={{ maxWidth: 700 }}>
                <Text type="secondary">Проходной балл: {active.quiz.pass_score}%</Text>
                {active.quiz.questions.map((q, qi) => (
                  <div key={qi} style={{ margin: '16px 0' }}>
                    <b>{qi + 1}. {q.q}</b>
                    <Radio.Group style={{ display: 'block', marginTop: 8 }}
                      value={quizAnswers[qi]} disabled={!!quizResult}
                      onChange={(e) => setQuizAnswers((a) => a.map((v, i) => (i === qi ? e.target.value : v)))}>
                      {q.options.map((opt, oi) => (
                        <Radio key={oi} value={oi} style={{ display: 'block', marginBottom: 4 }}>{opt}</Radio>
                      ))}
                    </Radio.Group>
                  </div>
                ))}
                {quizResult ? (
                  <Alert
                    type={quizResult.passed ? 'success' : 'error'} showIcon
                    message={quizResult.passed ? 'Тест пройден!' : 'Тест не пройден'}
                    description={`Результат: ${quizResult.score}% (${quizResult.correct_count} из ${quizResult.total})`}
                    action={!quizResult.passed && <Button size="small" onClick={() => setQuizResult(null)}>Ещё раз</Button>}
                  />
                ) : (
                  <Button type="primary" disabled={!course.enrolled || quizAnswers.some((a) => a < 0)} onClick={submitQuiz}>
                    Отправить ответы
                  </Button>
                )}
              </div>
            )}

            {!mediaLoading && active.lesson_type !== 'text' && active.lesson_type !== 'quiz'
              && !mediaUrl && !active.hls_ready && (
              <Paragraph type="secondary">Материал ещё не загружен продавцом.</Paragraph>
            )}
          </div>
        )}
      </Content>

      <Modal
        title="Получить сертификат"
        open={certModal}
        onCancel={() => setCertModal(false)}
        onOk={confirmCertificate}
        okText="Скачать сертификат"
      >
        <p>Укажите ФИО так, как оно должно быть напечатано в сертификате:</p>
        <Input
          value={certName}
          onChange={(e) => setCertName(e.target.value)}
          placeholder="Иванов Иван Иванович"
          onPressEnter={confirmCertificate}
        />
      </Modal>
    </Layout>
  )
}
