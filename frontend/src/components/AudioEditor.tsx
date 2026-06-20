import React from 'react'
import { Box, Typography, Paper } from '@mui/material'

function AudioEditor() {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        音频编辑
      </Typography>
      <Box sx={{ mt: 2 }}>
        <Typography color="text.secondary">
          编辑和剪辑音频文件
        </Typography>
      </Box>
    </Paper>
  )
}

export default AudioEditor
