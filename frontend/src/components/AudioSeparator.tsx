import React from 'react'
import { Box, Typography, Paper } from '@mui/material'

function AudioSeparator() {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        音源分离
      </Typography>
      <Box sx={{ mt: 2 }}>
        <Typography color="text.secondary">
          分离音频中的人声和伴奏
        </Typography>
      </Box>
    </Paper>
  )
}

export default AudioSeparator
