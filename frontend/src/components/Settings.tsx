import React from 'react'
import { Box, Typography, Paper } from '@mui/material'

function Settings() {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        设置
      </Typography>
      <Box sx={{ mt: 2 }}>
        <Typography color="text.secondary">
          应用程序设置和配置
        </Typography>
      </Box>
    </Paper>
  )
}

export default Settings
