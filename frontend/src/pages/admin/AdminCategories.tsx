import { useEffect, useState } from 'react'
import { Tree, Button, Modal, Form, Input, Select, message, Typography, Popconfirm, Space, Tag } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'
import type { Category } from '@/types'

const { Title } = Typography

const kindMeta: Record<string, { label: string; color: string }> = {
  digital: { label: 'цифровые', color: 'purple' },
  course: { label: 'курсы', color: 'gold' },
}

export default function AdminCategories() {
  const [categories, setCategories] = useState<Category[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)
  const [form] = Form.useForm()
  const [reassignFor, setReassignFor] = useState<Category | null>(null)
  const [reassignTarget, setReassignTarget] = useState<number | undefined>()

  const flattenCategories = (cats: Category[]): Category[] =>
    cats.flatMap((c) => [c, ...flattenCategories(c.children || [])])

  const load = () => {
    adminApi.listCategories().then(setCategories)
  }

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (cat: Category) => {
    setEditing(cat)
    form.setFieldsValue(cat)
    setModalOpen(true)
  }

  const handleSubmit = async (values: any) => {
    try {
      if (editing) {
        await adminApi.updateCategory(editing.id, values)
        message.success('Категория обновлена')
      } else {
        await adminApi.createCategory(values)
        message.success('Категория создана')
      }
      setModalOpen(false)
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleDelete = async (cat: Category) => {
    try {
      await adminApi.deleteCategory(cat.id)
      message.success('Категория удалена')
      load()
    } catch (e: any) {
      const detail: string = e.response?.data?.detail || 'Ошибка удаления'
      // Backend refuses to orphan products — offer to move them elsewhere first.
      if (detail.includes('reassign_to') || detail.toLowerCase().includes('тов')) {
        setReassignFor(cat)
        setReassignTarget(undefined)
      } else {
        message.error(detail)
      }
    }
  }

  const confirmReassignDelete = async () => {
    if (!reassignFor || !reassignTarget) return
    try {
      await adminApi.deleteCategory(reassignFor.id, reassignTarget)
      message.success('Товары перенесены, категория удалена')
      setReassignFor(null)
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const toTreeData = (cats: Category[]): any[] =>
    cats.map((c) => ({
      key: c.id,
      title: (
        <Space>
          <span>{c.name}</span>
          {c.kind && kindMeta[c.kind] && <Tag color={kindMeta[c.kind].color}>{kindMeta[c.kind].label}</Tag>}
          <Button size="small" type="text" icon={<EditOutlined />} onClick={(e) => { e.stopPropagation(); openEdit(c) }} />
          <Popconfirm title="Удалить категорию?" onConfirm={() => handleDelete(c)}>
            <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={(e) => e.stopPropagation()} />
          </Popconfirm>
        </Space>
      ),
      children: c.children?.length ? toTreeData(c.children) : undefined,
    }))

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Категории</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Добавить категорию</Button>
      </div>

      <Tree treeData={toTreeData(categories)} defaultExpandAll showLine style={{ background: '#fff', padding: 16, borderRadius: 8 }} />

      <Modal
        title={editing ? 'Редактировать категорию' : 'Новая категория'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label="Название" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="slug" label="Slug (URL)" extra="Можно оставить пустым — сгенерируется автоматически">
            <Input placeholder="авто из названия" />
          </Form.Item>
          <Form.Item name="kind" label="Тип категории">
            <Select
              allowClear placeholder="Обычная (физические товары)"
              options={[
                { value: 'physical', label: 'Физические товары' },
                { value: 'digital', label: 'Цифровые товары' },
                { value: 'course', label: 'Курсы и обучение' },
              ]}
            />
          </Form.Item>
          <Form.Item name="parent_id" label="Родительская категория">
            <Select
              allowClear placeholder="Нет (корневая категория)"
              options={flattenCategories(categories)
                .filter((c) => c.id !== editing?.id)
                .map((c) => ({ value: c.id, label: c.name }))}
            />
          </Form.Item>
          <Form.Item name="sort_order" label="Порядок сортировки" initialValue={0}>
            <Input type="number" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Перенос товаров перед удалением"
        open={reassignFor !== null}
        onCancel={() => setReassignFor(null)}
        onOk={confirmReassignDelete}
        okText="Перенести и удалить"
        okButtonProps={{ disabled: !reassignTarget }}
      >
        <p>
          В категории «{reassignFor?.name}» есть товары. Выберите категорию, в которую их перенести,
          затем категория будет удалена.
        </p>
        <Select
          style={{ width: '100%' }}
          placeholder="Категория для переноса товаров"
          value={reassignTarget}
          onChange={setReassignTarget}
          showSearch optionFilterProp="label"
          options={flattenCategories(categories)
            .filter((c) => c.id !== reassignFor?.id)
            .map((c) => ({ value: c.id, label: c.name }))}
        />
      </Modal>
    </div>
  )
}
