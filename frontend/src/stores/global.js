import { defineStore } from 'pinia'
import { getCurrentInstance } from 'vue'

export const globalStore = defineStore('crm-global', () => {
  const app = getCurrentInstance()
  const { $dialog, $socket } = app.appContext.config.globalProperties

  let callMethod = () => {}
  let prepareCallMethod = () => {}

  function setMakeCall(value) {
    callMethod = value
  }

  function makeCall(number, context = null) {
    callMethod(number, context)
  }

  function setPrepareCall(value) {
    prepareCallMethod = value
  }

  function prepareCall(number = '', context = null) {
    prepareCallMethod(number, context)
  }

  return {
    $dialog,
    $socket,
    makeCall,
    setMakeCall,
    prepareCall,
    setPrepareCall,
  }
})
