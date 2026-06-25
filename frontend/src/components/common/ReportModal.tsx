import { useState } from 'react'
import { Modal, Form, Input, message } from 'antd'
import { reportsApi } from '@/api'

interface ReportModalProps {
  open: boolean
  onClose: () => void
  targetType: 'product' | 'shop' | 'user'
  targetId: number
  targetLabel?: string
}

/**
 * Modal for filing a report against a product, shop, or user. Backed by
 * POST /reports, which moderators review in the admin panel (/admin/reports).
 */
export default function ReportModal({ open, onClose, targetType, targetId, targetLabel }: ReportModalProps) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (values: { reason: string }) => {
    setSubmitting(true)
    try {
      await reportsApi.create({
        target_type: targetType,
        target_id: targetId,
        reason: values.reason,
      })
      message.success('Жалоба отправлена модераторам')
      form.resetFields()
      onClose()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Не удалось отправить жалобу')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title={`Пожаловаться${targetLabel ? `: ${targetLabel}` : ''}`}
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      okText="Отправить жалобу"
      okButtonProps={{ danger: true }}
      cancelText="Отмена"
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item
          name="reason"
          label="Опишите проблему"
          rules={[{ required: true, min: 10, message: 'Минимум 10 символов — опишите проблему подробнее' }]}
        >
          <Input.TextArea
            rows={4}
            placeholder="Например: товар не соответствует описанию, подозрение на подделку, мошенничество..."
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
