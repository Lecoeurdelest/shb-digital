import { describe, expect, it } from 'vitest'
import * as elementEntry from './element'
import * as headlessEntry from './index'
import * as reactEntry from './react'

describe('SDK public runtime contract', () => {
  it('keeps headless exports stable', () => {
    expect(Object.keys(headlessEntry).sort()).toEqual([
      'BankDigitalApiError',
      'ChatTurnAssembler',
      'SseDataParser',
      'createBankDigitalClient',
      'isApiErrorPayload',
    ])
  })

  it('keeps React exports stable', () => {
    expect(Object.keys(reactEntry).sort()).toEqual([
      'BankConversation',
      'BankConversationProvider',
      'Cards',
      'Composer',
      'CustomerAssistant',
      'ErrorNotice',
      'Frame',
      'Header',
      'Messages',
      'RmCopilot',
      'Status',
      'bankDigitalStyles',
      'useBankConversation',
    ])
  })

  it('keeps element exports and custom tag names stable', () => {
    expect(Object.keys(elementEntry).sort()).toEqual([
      'CUSTOMER_ASSISTANT_TAG',
      'RM_COPILOT_TAG',
      'defineBankDigitalElements',
      'mountCustomerAssistant',
      'mountRmCopilot',
    ])
    expect(elementEntry.CUSTOMER_ASSISTANT_TAG).toBe('bank-digital-customer-assistant')
    expect(elementEntry.RM_COPILOT_TAG).toBe('bank-digital-rm-copilot')
  })
})
