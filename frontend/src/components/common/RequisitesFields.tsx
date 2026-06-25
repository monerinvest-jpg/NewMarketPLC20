import { Form, Input, Select, Typography, Alert } from 'antd'
import type { FormInstance } from 'antd'

const { Text } = Typography

/**
 * Requisites form fields. Shows/requires different fields depending on the
 * selected tax regime. Must be used inside an Ant Form. The parent reads values
 * via the shared form instance.
 */
export default function RequisitesFields({ form }: { form: FormInstance }) {
  const regime = Form.useWatch('tax_regime', form)

  return (
    <>
      <Form.Item name="tax_regime" label="Налоговый режим" rules={[{ required: true, message: 'Выберите режим' }]}>
        <Select
          placeholder="Выберите режим"
          options={[
            { value: 'self_employed', label: 'Самозанятость (НПД)' },
            { value: 'individual', label: 'ИП — индивидуальный предприниматель' },
            { value: 'company', label: 'ООО' },
          ]}
        />
      </Form.Item>

      {regime === 'self_employed' && (
        <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="Для самозанятых достаточно ФИО и ИНН (12 цифр). Банковские реквизиты — для выплат." />
      )}
      {regime === 'individual' && (
        <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="Для ИП требуются ФИО, ИНН и ОГРНИП." />
      )}
      {regime === 'company' && (
        <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="Для ООО требуются наименование, ИНН, КПП, ОГРН и юридический адрес." />
      )}

      <Form.Item
        name="legal_name"
        label={regime === 'company' ? 'Полное наименование' : 'ФИО'}
        rules={[{ required: true, message: 'Обязательное поле' }]}
      >
        <Input placeholder={regime === 'company' ? 'ООО «Ромашка»' : 'Иванов Иван Иванович'} />
      </Form.Item>

      <Form.Item
        name="inn" label="ИНН"
        rules={[
          { required: true, message: 'Укажите ИНН' },
          { pattern: /^\d{10,12}$/, message: 'ИНН — 10 или 12 цифр' },
        ]}
      >
        <Input placeholder="10 или 12 цифр" maxLength={12} />
      </Form.Item>

      {(regime === 'individual' || regime === 'company') && (
        <Form.Item
          name="ogrn" label={regime === 'company' ? 'ОГРН' : 'ОГРНИП'}
          rules={[{ required: true, message: 'Обязательное поле' }]}
        >
          <Input placeholder={regime === 'company' ? '13 цифр' : '15 цифр'} maxLength={15} />
        </Form.Item>
      )}

      {regime === 'company' && (
        <>
          <Form.Item name="kpp" label="КПП" rules={[{ required: true, message: 'Укажите КПП' }]}>
            <Input placeholder="9 цифр" maxLength={9} />
          </Form.Item>
          <Form.Item name="legal_address" label="Юридический адрес" rules={[{ required: true, message: 'Укажите адрес' }]}>
            <Input.TextArea rows={2} placeholder="Город, улица, дом, офис" />
          </Form.Item>
        </>
      )}

      <Text type="secondary" style={{ display: 'block', margin: '8px 0' }}>Фискализация чеков (54-ФЗ)</Text>
      <Form.Item
        name="vat_code" label="Ставка НДС"
        tooltip="Используется в кассовом чеке. Если не выбрать — применится ставка платформы по умолчанию."
      >
        <Select
          allowClear placeholder="По умолчанию (платформа)"
          options={[
            { value: 1, label: 'Без НДС' },
            { value: 2, label: 'НДС 0%' },
            { value: 3, label: 'НДС 10%' },
            { value: 4, label: 'НДС 20%' },
            { value: 5, label: 'НДС 10/110' },
            { value: 6, label: 'НДС 20/120' },
          ]}
        />
      </Form.Item>
      <Form.Item
        name="tax_system_code" label="Система налогообложения (СНО)"
        tooltip="Передаётся в чек, если на кассе используется несколько СНО."
      >
        <Select
          allowClear placeholder="По умолчанию (платформа)"
          options={[
            { value: 1, label: 'ОСН' },
            { value: 2, label: 'УСН (доход)' },
            { value: 3, label: 'УСН (доход − расход)' },
            { value: 4, label: 'ЕНВД' },
            { value: 5, label: 'ЕСХН' },
            { value: 6, label: 'Патент' },
          ]}
        />
      </Form.Item>

      <Text type="secondary" style={{ display: 'block', margin: '8px 0' }}>Банковские реквизиты (для выплат)</Text>
      <Form.Item name="bank_account" label="Расчётный счёт">
        <Input placeholder="20 цифр" maxLength={20} />
      </Form.Item>
      <Form.Item name="bank_name" label="Банк">
        <Input placeholder="Наименование банка" />
      </Form.Item>
      <Form.Item name="bik" label="БИК">
        <Input placeholder="9 цифр" maxLength={9} />
      </Form.Item>
      <Form.Item name="corr_account" label="Корр. счёт">
        <Input placeholder="20 цифр" maxLength={20} />
      </Form.Item>
    </>
  )
}
