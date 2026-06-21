import axios from 'axios'
import { io, Socket } from 'socket.io-client'

const API_BASE_URL = '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

let socket: Socket | null = null

export const connectSocket = () => {
  if (!socket) {
    socket = io('/')
  }
  return socket
}

export const disconnectSocket = () => {
  if (socket) {
    socket.disconnect()
    socket = null
  }
}

export const uploadFile = async (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post('/files/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export const getFiles = async () => {
  const response = await api.get('/files')
  return response.data
}

export const getFile = async (id: number) => {
  const response = await api.get(`/files/${id}`)
  return response.data
}

export const deleteFile = async (id: number) => {
  const response = await api.delete(`/files/${id}`)
  return response.data
}

export const downloadFile = async (id: number) => {
  const response = await api.get(`/files/${id}/download`, {
    responseType: 'blob',
  })
  return response.data
}

export const extractAudio = async (videoFileId: number, outputFormat: string, bitrate?: string) => {
  const response = await api.post('/audio/extract', {
    video_file_id: videoFileId,
    output_format: outputFormat,
    bitrate: bitrate || '192k',
  })
  return response.data
}

export const clipAudio = async (
  audioFileId: number,
  operation: 'extract' | 'delete',
  startTime: number,
  endTime: number,
  outputFormat?: string
) => {
  const response = await api.post('/audio/clip', {
    audio_file_id: audioFileId,
    operation,
    start_time: startTime,
    end_time: endTime,
    output_format: outputFormat || 'mp3',
  })
  return response.data
}

export const separateAudio = async (audioFileId: number, stems: string[], engine?: string, model?: string) => {
  const response = await api.post('/audio/separate', {
    audio_file_id: audioFileId,
    stems,
    engine: engine || 'demucs',
    model: model || 'htdemucs_ft',
  })
  return response.data
}

export const getTasks = async (taskType?: string, status?: string) => {
  const params: any = {}
  if (taskType) params.task_type = taskType
  if (status) params.status = status
  const response = await api.get('/tasks', { params })
  return response.data
}

export const getTask = async (id: number) => {
  const response = await api.get(`/tasks/${id}`)
  return response.data
}

export const cancelTask = async (id: number) => {
  const response = await api.delete(`/tasks/${id}`)
  return response.data
}

export const getConfig = async () => {
  const response = await api.get('/config')
  return response.data
}

export const updateConfig = async (config: Record<string, string>) => {
  const response = await api.put('/config', config)
  return response.data
}

export const resetConfig = async () => {
  const response = await api.post('/config/reset')
  return response.data
}

export const getSeparationStatus = async () => {
  const response = await api.get('/audio/separation/status')
  return response.data
}

export const scanModels = async () => {
  const response = await api.get('/config/models/scan')
  return response.data
}

export const validateModelDir = async (modelDir: string) => {
  const response = await api.post('/config/models/validate', { model_dir: modelDir })
  return response.data
}

export const startSubtitle = async (audioFileId: number, model?: string, language?: string) => {
  const response = await api.post('/audio/subtitle', {
    audio_file_id: audioFileId,
    model,
    language: language || 'auto',
  })
  return response.data
}

export const getSubtitleStatus = async () => {
  const response = await api.get('/audio/subtitle/status')
  return response.data
}

export const getSubtitleResult = async (taskId: number) => {
  const response = await api.get(`/audio/subtitle/${taskId}/result`)
  return response.data
}

export const exportSubtitle = async (taskId: number, format: string, segments?: any[]) => {
  const response = await api.post(
    `/audio/subtitle/${taskId}/export`,
    { format, segments },
    { responseType: 'blob' }
  )
  return response
}

export const startTTS = async (params: {
  text: string
  mode: string
  speaker?: string
  ref_audio_id?: number
  ref_text?: string
  emotions?: Array<{sentence: string, instruct: string}>
  speed?: number
  temperature?: number
  language?: string
}) => {
  const response = await api.post('/audio/tts', params)
  return response.data
}

export const getTTSStatus = async () => {
  const response = await api.get('/audio/tts/status')
  return response.data
}

export const getTTSSpeakers = async () => {
  const response = await api.get('/audio/tts/speakers')
  return response.data
}

export const analyzeTTSEmotion = async (text: string) => {
  const response = await api.post('/audio/tts/analyze', { text })
  return response.data
}

export const getSAMStatus = async () => {
  const response = await api.get('/image/status')
  return response.data
}

export const loadSAMModel = async () => {
  const response = await api.post('/image/load')
  return response.data
}

export const detectImageObjects = async (imageFile: File, prompt: string) => {
  const formData = new FormData()
  formData.append('image', imageFile)
  formData.append('prompt', prompt)
  const response = await api.post('/image/detect', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export const extractImageObject = async (imageFile: File, mask: string, box?: number[]) => {
  const formData = new FormData()
  formData.append('image', imageFile)
  formData.append('mask', mask)
  if (box) {
    formData.append('box', JSON.stringify(box))
  }
  const response = await api.post('/image/extract', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    responseType: 'blob',
  })
  return response.data
}

export const removeImageBackground = async (imageFile: File, prompt?: string) => {
  const formData = new FormData()
  formData.append('image', imageFile)
  if (prompt) {
    formData.append('prompt', prompt)
  }
  const response = await api.post('/image/remove-background', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    responseType: 'blob',
  })
  return response.data
}

// BiRefNet API functions
export const getBirefnetModels = async () => {
  const response = await api.get('/birefnet/models')
  return response.data
}

export const loadBirefnetModel = async (modelType: string) => {
  const response = await api.post('/birefnet/load-model', { model_type: modelType })
  return response.data
}

export const segmentBirefnetImage = async (imageFile: File, modelType: string = 'general') => {
  const formData = new FormData()
  formData.append('image', imageFile)
  formData.append('model_type', modelType)
  const response = await api.post('/birefnet/segment', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export const removeBirefnetBackground = async (imageFile: File, modelType: string = 'general') => {
  const formData = new FormData()
  formData.append('image', imageFile)
  formData.append('model_type', modelType)
  const response = await api.post('/birefnet/remove-background', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    responseType: 'blob',
  })
  return response.data
}
