import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Button, Collapse, Modal, Form, Input, Select, Switch, Upload, Tag,
  Typography, message, Space, Popconfirm, Spin, Empty, InputNumber, Radio, Divider,
} from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined, ArrowLeftOutlined,
  PlayCircleOutlined, FilePdfOutlined, FileTextOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { coursesApi } from '@/api'
import type { CourseDetail, CourseLessonNode } from '@/types'

const { Title, Text } = Typography

const typeMeta: Record<string, { icon: JSX.Element; label: string }> = {
  video: { icon: <PlayCircleOutlined />, label: 'Видео' },
  pdf: { icon: <FilePdfOutlined />, label: 'PDF' },
  text: { icon: <FileTextOutlined />, label: 'Текст' },
  quiz: { icon: <CheckCircleOutlined />, label: 'Тест' },
}

type QuizQ = { q: string; options: string[]; correct: number }
const emptyQuiz = { pass_score: 70, questions: [] as QuizQ[] }

export default function SellerCourseBuilder() {
  const { productId } = useParams()
  const pid = Number(productId)
  const navigate = useNavigate()
  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [instructor, setInstructor] = useState('')

  const [moduleModal, setModuleModal] = useState(false)
  const [moduleForm] = Form.useForm()

  const [lessonModal, setLessonModal] = useState<{ moduleId: number; lesson?: CourseLessonNode } | null>(null)
  const [lessonForm] = Form.useForm()
  const lessonType = Form.useWatch('lesson_type', lessonForm)
  const [quiz, setQuiz] = useState<{ pass_score: number; questions: QuizQ[] }>(emptyQuiz)

  // ---- quiz editor helpers (immutable updates) ----
  const setQ = (qi: number, patch: Partial<QuizQ>) =>
    setQuiz((s) => ({ ...s, questions: s.questions.map((q, i) => (i === qi ? { ...q, ...patch } : q)) }))
  const addQuestion = () => setQuiz((s) => ({ ...s, questions: [...s.questions, { q: '', options: ['', ''], correct: 0 }] }))
  const removeQuestion = (qi: number) => setQuiz((s) => ({ ...s, questions: s.questions.filter((_, i) => i !== qi) }))
  const setOption = (qi: number, oi: number, val: string) =>
    setQ(qi, { options: quiz.questions[qi].options.map((o, i) => (i === oi ? val : o)) })
  const addOption = (qi: number) => setQ(qi, { options: [...quiz.questions[qi].options, ''] })
  const removeOption = (qi: number, oi: number) => {
    const q = quiz.questions[qi]
    const options = q.options.filter((_, i) => i !== oi)
    setQ(qi, { options, correct: q.correct >= options.length ? 0 : q.correct })
  }

  const load = async () => {
    try {
      const c = await coursesApi.builder(pid)
      setCourse(c)
      setInstructor(c.cert_instructor || '')
    } catch {
      message.error('Не удалось открыть курс')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [pid])

  const saveCertSettings = async () => {
    await coursesApi.updateSettings(pid, { cert_instructor: instructor })
    message.success('Настройки сертификата сохранены')
    load()
  }

  const uploadCertLogo = async (file: File) => {
    try {
      await coursesApi.uploadCertLogo(pid, file)
      message.success('Логотип загружен')
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка загрузки')
    }
  }

  const addModule = async (v: any) => {
    await coursesApi.addModule(pid, v)
    setModuleModal(false)
    moduleForm.resetFields()
    load()
  }

  const deleteModule = async (moduleId: number) => {
    await coursesApi.deleteModule(pid, moduleId)
    load()
  }

  const openLesson = (moduleId: number, lesson?: CourseLessonNode) => {
    setLessonModal({ moduleId, lesson })
    lessonForm.setFieldsValue(lesson ?? { lesson_type: 'video', is_preview: false, sort_order: 0 })
    if (lesson?.quiz) {
      setQuiz({
        pass_score: lesson.quiz.pass_score ?? 70,
        questions: (lesson.quiz.questions || []).map((q) => ({ q: q.q, options: q.options, correct: q.correct ?? 0 })),
      })
    } else {
      setQuiz(emptyQuiz)
    }
  }

  const submitLesson = async (v: any) => {
    if (!lessonModal) return
    if (v.lesson_type === 'quiz') {
      if (quiz.questions.length === 0) { message.error('Добавьте хотя бы один вопрос'); return }
      v.quiz = quiz
    }
    try {
      if (lessonModal.lesson) {
        await coursesApi.updateLesson(pid, lessonModal.lesson.id, v)
      } else {
        await coursesApi.addLesson(pid, lessonModal.moduleId, v)
      }
      message.success('Сохранено')
      setLessonModal(null)
      lessonForm.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const deleteLesson = async (lessonId: number) => {
    await coursesApi.deleteLesson(pid, lessonId)
    load()
  }

  const uploadFile = async (lessonId: number, file: File) => {
    try {
      await coursesApi.uploadLessonFile(pid, lessonId, file)
      message.success('Файл загружен')
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка загрузки')
    }
  }

  if (loading) return <div className="flex justify-center py-20"><Spin size="large" /></div>
  if (!course) return <Empty description="Курс недоступен" />

  return (
    <div className="max-w-4xl mx-auto py-4">
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/products')}>Назад</Button>
        <Title level={3} style={{ margin: 0 }}>Курс: {course.title}</Title>
      </Space>

      <Card size="small" title="Сертификат курса" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space.Compact style={{ width: '100%', maxWidth: 520 }}>
            <Input value={instructor} onChange={(e) => setInstructor(e.target.value)}
              placeholder="Преподаватель / подпись (печатается в сертификате)" />
            <Button type="primary" onClick={saveCertSettings}>Сохранить</Button>
          </Space.Compact>
          <Space>
            <Upload showUploadList={false} accept="image/*" beforeUpload={(f) => { uploadCertLogo(f as File); return false }}>
              <Button icon={<UploadOutlined />}>{course.has_cert_logo ? 'Заменить логотип' : 'Загрузить логотип'}</Button>
            </Upload>
            {course.has_cert_logo && <Tag color="blue">логотип загружен</Tag>}
            <Text type="secondary">Кириллица в сертификате поддерживается.</Text>
          </Space>
        </Space>
      </Card>

      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModuleModal(true)}>Добавить модуль</Button>
      </div>

      {course.modules.length === 0 ? (
        <Empty description="Пока нет модулей. Добавьте первый." />
      ) : (
        <Collapse
          defaultActiveKey={course.modules.map((m) => String(m.id))}
          items={course.modules.map((m) => ({
            key: String(m.id),
            label: <b>{m.title}</b>,
            extra: (
              <Popconfirm title="Удалить модуль и его уроки?" onConfirm={(e) => { e?.stopPropagation(); deleteModule(m.id) }}>
                <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={(e) => e.stopPropagation()} />
              </Popconfirm>
            ),
            children: (
              <>
                {m.lessons.map((l) => (
                  <Card key={l.id} size="small" style={{ marginBottom: 8 }}>
                    <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                      <Space>
                        {typeMeta[l.lesson_type].icon}
                        <span>{l.title}</span>
                        <Tag>{typeMeta[l.lesson_type].label}</Tag>
                        {l.is_preview && <Tag color="green">превью</Tag>}
                        {(l.lesson_type === 'video' || l.lesson_type === 'pdf') && (l.has_file
                          ? <Tag color="blue" icon={<CheckCircleOutlined />}>{l.lesson_type === 'video' && l.hls_ready ? 'HLS готов' : 'файл'}</Tag>
                          : <Tag color="orange">нет файла</Tag>)}
                      </Space>
                      <Space>
                        {(l.lesson_type === 'video' || l.lesson_type === 'pdf') && (
                          <Upload showUploadList={false} beforeUpload={(f) => { uploadFile(l.id, f as File); return false }}>
                            <Button size="small" icon={<UploadOutlined />}>{l.has_file ? 'Заменить' : 'Загрузить'}</Button>
                          </Upload>
                        )}
                        <Button size="small" icon={<EditOutlined />} onClick={() => openLesson(m.id, l)} />
                        <Popconfirm title="Удалить урок?" onConfirm={() => deleteLesson(l.id)}>
                          <Button size="small" danger icon={<DeleteOutlined />} />
                        </Popconfirm>
                      </Space>
                    </Space>
                  </Card>
                ))}
                <Button type="dashed" icon={<PlusOutlined />} onClick={() => openLesson(m.id)} block>Добавить урок</Button>
              </>
            ),
          }))}
        />
      )}

      {/* Module modal */}
      <Modal title="Новый модуль" open={moduleModal} onCancel={() => setModuleModal(false)} onOk={() => moduleForm.submit()}>
        <Form form={moduleForm} layout="vertical" onFinish={addModule}>
          <Form.Item name="title" label="Название модуля" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="sort_order" label="Порядок" initialValue={0}>
            <Input type="number" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Lesson modal */}
      <Modal
        title={lessonModal?.lesson ? 'Редактировать урок' : 'Новый урок'}
        open={lessonModal !== null}
        onCancel={() => setLessonModal(null)}
        onOk={() => lessonForm.submit()}
      >
        <Form form={lessonForm} layout="vertical" onFinish={submitLesson}>
          <Form.Item name="title" label="Название урока" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="lesson_type" label="Тип урока" rules={[{ required: true }]}>
            <Select
              disabled={!!lessonModal?.lesson}
              options={[
                { value: 'video', label: 'Видео' },
                { value: 'pdf', label: 'PDF' },
                { value: 'text', label: 'Текст' },
                { value: 'quiz', label: 'Тест' },
              ]}
            />
          </Form.Item>
          {lessonType === 'text' && (
            <Form.Item name="text_body" label="Текст урока (HTML разрешён)">
              <Input.TextArea rows={8} />
            </Form.Item>
          )}
          {lessonType === 'quiz' && (
            <div style={{ marginBottom: 16 }}>
              <Divider orientation="left">Вопросы теста</Divider>
              <Space style={{ marginBottom: 8 }}>
                <Text>Проходной балл, %:</Text>
                <InputNumber min={0} max={100} value={quiz.pass_score}
                  onChange={(v) => setQuiz((s) => ({ ...s, pass_score: Number(v) || 0 }))} />
              </Space>
              {quiz.questions.map((q, qi) => (
                <Card key={qi} size="small" style={{ marginBottom: 8 }}
                  title={`Вопрос ${qi + 1}`}
                  extra={<Button size="small" danger icon={<DeleteOutlined />} onClick={() => removeQuestion(qi)} />}>
                  <Input placeholder="Текст вопроса" value={q.q}
                    onChange={(e) => setQ(qi, { q: e.target.value })} style={{ marginBottom: 8 }} />
                  <Radio.Group value={q.correct} onChange={(e) => setQ(qi, { correct: e.target.value })} style={{ width: '100%' }}>
                    {q.options.map((opt, oi) => (
                      <div key={oi} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <Radio value={oi} />
                        <Input placeholder={`Вариант ${oi + 1}`} value={opt}
                          onChange={(e) => setOption(qi, oi, e.target.value)} />
                        {q.options.length > 2 && (
                          <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => removeOption(qi, oi)} />
                        )}
                      </div>
                    ))}
                  </Radio.Group>
                  <Button size="small" type="dashed" onClick={() => addOption(qi)}>+ вариант</Button>
                  <div style={{ marginTop: 4 }}><Text type="secondary">Отметьте правильный вариант радиокнопкой.</Text></div>
                </Card>
              ))}
              <Button type="dashed" icon={<PlusOutlined />} onClick={addQuestion} block>Добавить вопрос</Button>
            </div>
          )}
          {lessonType === 'video' && (
            <Form.Item name="duration_seconds" label="Длительность, сек" initialValue={0}>
              <Input type="number" />
            </Form.Item>
          )}
          <Form.Item name="is_preview" label="Бесплатное превью" valuePropName="checked" initialValue={false}>
            <Switch />
          </Form.Item>
          <Form.Item name="sort_order" label="Порядок" initialValue={0}>
            <Input type="number" />
          </Form.Item>
          {!lessonModal?.lesson && lessonType !== 'text' && (
            <Text type="secondary">Файл можно будет загрузить после создания урока.</Text>
          )}
        </Form>
      </Modal>
    </div>
  )
}
