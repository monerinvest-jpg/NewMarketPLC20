import { useEffect, useState } from 'react'
import {
  Typography, Table, Button, Modal, Form, Input, Select, Switch, Space, message,
  Popconfirm, Drawer, Tag, InputNumber,
} from 'antd'
import { PlusOutlined, ReadOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'

const { Title } = Typography

const levels = [
  { value: 'beginner', label: 'Начальный' },
  { value: 'intermediate', label: 'Средний' },
  { value: 'advanced', label: 'Продвинутый' },
]

export default function AdminAcademy() {
  const [courses, setCourses] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [courseModal, setCourseModal] = useState<{ open: boolean; edit?: any }>({ open: false })
  const [cForm] = Form.useForm()

  const [lessonsDrawer, setLessonsDrawer] = useState<{ open: boolean; course?: any }>({ open: false })
  const [lessons, setLessons] = useState<any[]>([])
  const [lessonModal, setLessonModal] = useState<{ open: boolean; edit?: any }>({ open: false })
  const [lForm] = Form.useForm()

  const load = () => { setLoading(true); adminApi.academyCourses().then(setCourses).finally(() => setLoading(false)) }
  useEffect(() => { load() }, [])

  const saveCourse = async () => {
    const v = await cForm.validateFields()
    try {
      if (courseModal.edit) await adminApi.academyUpdateCourse(courseModal.edit.id, v)
      else await adminApi.academyCreateCourse(v)
      message.success('Сохранено'); setCourseModal({ open: false }); cForm.resetFields(); load()
    } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
  }

  const togglePublish = async (c: any) => {
    await adminApi.academyUpdateCourse(c.id, { is_published: !c.is_published }); load()
  }

  const openLessons = async (course: any) => {
    setLessonsDrawer({ open: true, course })
    setLessons(await adminApi.academyLessons(course.id))
  }
  const reloadLessons = async () => { if (lessonsDrawer.course) setLessons(await adminApi.academyLessons(lessonsDrawer.course.id)) }

  const saveLesson = async () => {
    const v = await lForm.validateFields()
    try {
      if (lessonModal.edit) await adminApi.academyUpdateLesson(lessonModal.edit.id, v)
      else await adminApi.academyAddLesson(lessonsDrawer.course.id, v)
      message.success('Сохранено'); setLessonModal({ open: false }); lForm.resetFields(); reloadLessons()
    } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <Title level={3} style={{ marginTop: 0 }}>Академия продавца</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { cForm.resetFields(); cForm.setFieldsValue({ level: 'beginner', is_published: false }); setCourseModal({ open: true }) }}>
          Новый курс
        </Button>
      </div>

      <Table
        loading={loading} rowKey="id" dataSource={courses} pagination={false}
        columns={[
          { title: 'Курс', dataIndex: 'title' },
          { title: 'Уровень', dataIndex: 'level', render: (v) => levels.find((l) => l.value === v)?.label || v },
          { title: 'Уроков', dataIndex: 'lesson_count', width: 80 },
          { title: 'Опубликован', dataIndex: 'is_published', render: (v, c) => <Switch checked={v} onChange={() => togglePublish(c)} /> },
          {
            title: '', render: (_, c) => (
              <Space>
                <Button size="small" icon={<ReadOutlined />} onClick={() => openLessons(c)}>Уроки</Button>
                <Button size="small" onClick={() => { cForm.setFieldsValue(c); setCourseModal({ open: true, edit: c }) }}>Изм.</Button>
                <Popconfirm title="Удалить курс?" onConfirm={async () => { await adminApi.academyDeleteCourse(c.id); load() }}>
                  <Button size="small" danger>Удалить</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal title={courseModal.edit ? 'Курс' : 'Новый курс'} open={courseModal.open} onOk={saveCourse} onCancel={() => setCourseModal({ open: false })} okText="Сохранить">
        <Form form={cForm} layout="vertical">
          <Form.Item name="title" label="Название" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Описание"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="cover_url" label="Обложка (URL)"><Input /></Form.Item>
          <Space>
            <Form.Item name="level" label="Уровень"><Select options={levels} style={{ width: 160 }} /></Form.Item>
            <Form.Item name="sort_order" label="Порядок"><InputNumber min={0} /></Form.Item>
            <Form.Item name="is_published" label="Опубликован" valuePropName="checked"><Switch /></Form.Item>
          </Space>
        </Form>
      </Modal>

      <Drawer
        title={`Уроки: ${lessonsDrawer.course?.title || ''}`} width={640}
        open={lessonsDrawer.open} onClose={() => setLessonsDrawer({ open: false })}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => { lForm.resetFields(); lForm.setFieldsValue({ content_type: 'text', sort_order: lessons.length }); setLessonModal({ open: true }) }}>Урок</Button>}
      >
        <Table
          rowKey="id" size="small" pagination={false} dataSource={lessons}
          columns={[
            { title: '#', dataIndex: 'sort_order', width: 40 },
            { title: 'Урок', dataIndex: 'title' },
            { title: 'Тип', dataIndex: 'content_type', render: (v) => <Tag>{v}</Tag> },
            {
              title: '', render: (_, l) => (
                <Space>
                  <Button size="small" onClick={() => { lForm.setFieldsValue(l); setLessonModal({ open: true, edit: l }) }}>Изм.</Button>
                  <Popconfirm title="Удалить урок?" onConfirm={async () => { await adminApi.academyDeleteLesson(l.id); reloadLessons() }}>
                    <Button size="small" danger>×</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Drawer>

      <Modal title={lessonModal.edit ? 'Урок' : 'Новый урок'} open={lessonModal.open} onOk={saveLesson} onCancel={() => setLessonModal({ open: false })} okText="Сохранить">
        <Form form={lForm} layout="vertical">
          <Form.Item name="title" label="Название" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="content_type" label="Тип контента">
            <Select options={[{ value: 'text', label: 'Текст' }, { value: 'video', label: 'Видео' }, { value: 'link', label: 'Ссылка' }]} />
          </Form.Item>
          <Form.Item name="body" label="Текст (markdown)"><Input.TextArea rows={5} /></Form.Item>
          <Form.Item name="video_url" label="URL видео / ссылки"><Input placeholder="https://..." /></Form.Item>
          <Form.Item name="sort_order" label="Порядок"><InputNumber min={0} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
