import React from 'react'
import { Box, Typography, Paper } from '@mui/material'

function AudioExtractor() {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        音频提取
      </Typography>
      <Box sx={{ mt: 2 }}>
        <Typography color="text.secondary">
          从视频文件中提取音频轨道
        </Typography>
      </Box>
    </Paper>
  )
}

export default AudioExtractor
