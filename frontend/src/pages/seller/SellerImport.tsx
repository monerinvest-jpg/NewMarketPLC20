import { useState } from 'react'
import { Card, Typography, Upload, Button, message, Alert, List } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { productsApi } from '@/api'

const { Title, Paragraph, Text } = Typography

export default function SellerImport() {
  const [result, setResult] = useState<{ created: number; errors: string[]; total_rows: number } | null>(null)
  const [uploading, setUploading] = useState(false)

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const res = await productsApi.importCsv(file)
      setResult(res)
      message.success(`Импортировано товаров: ${res.created}`)
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка импорта')
    } finally {
      setUploading(false)
    }
    return false
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <Title level={3}>Импорт товаров из CSV</Title>
      <Card>
        <Paragraph>
          Загрузите CSV-файл со столбцами: <Text code>title</Text>, <Text code>description</Text>,{' '}
          <Text code>price</Text>, <Text code>quantity</Text>, <Text code>category_id</Text>,{' '}
          <Text code>weight_g</Text> (необяз.), <Text code>compare_at_price</Text> (необяз.).
        </Paragraph>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          Первая строка — заголовки. Кодировка UTF-8 или Windows-1251. Товары попадут на модерацию, если она включена.
        </Paragraph>

        <Upload accept=".csv" showUploadList={false} beforeUpload={handleUpload}>
          <Button icon={<UploadOutlined />} loading={uploading} type="primary">Выбрать CSV-файл</Button>
        </Upload>
      </Card>

      {result && (
        <Card style={{ marginTop: 16 }}>
          <Alert
            type={result.errors.length === 0 ? 'success' : 'warning'}
            message={`Импортировано ${result.created} из ${result.total_rows} строк`}
            style={{ marginBottom: result.errors.length ? 12 : 0 }}
          />
          {result.errors.length > 0 && (
            <List
              size="small"
              header={<Text strong>Ошибки</Text>}
              dataSource={result.errors}
              renderItem={(err) => <List.Item><Text type="danger" style={{ fontSize: 12 }}>{err}</Text></List.Item>}
            />
          )}
        </Card>
      )}
    </div>
  )
}
