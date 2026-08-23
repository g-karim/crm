import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const readSource = (path) => readFileSync(resolve(process.cwd(), path), 'utf8')

const leadSource = readSource('src/pages/Lead.vue')
const mobileLeadSource = readSource('src/pages/MobileLead.vue')
const assignToSource = readSource('src/components/AssignToBody.vue')
const dealSource = readSource('src/pages/Deal.vue')

describe('lead assignment permissions', () => {
  it('shows assignment controls only with record-level write permission', () => {
    for (let source of [leadSource, mobileLeadSource]) {
      expect(source).toContain('v-if="canWrite"')
      expect(source).toContain(
        'permissions.data?.permissions?.write || false',
      )
    }
  })

  it('refreshes CRM users and blocks selection while a Lead picker loads', () => {
    expect(assignToSource).toContain("props.doctype === 'CRM Lead'")
    expect(assignToSource).toContain('await users.reload()')
    expect(assignToSource).toContain(':disabled="refreshingUsers"')
  })

  it('does not gate Deal assignment controls with the Lead rule', () => {
    expect(dealSource).toContain(
      '<AssignTo v-model="assignees.data" doctype="CRM Deal"',
    )
  })
})
