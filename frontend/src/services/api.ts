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
