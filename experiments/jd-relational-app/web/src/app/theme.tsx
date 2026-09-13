'use client';
import { createTheme, ThemeProvider, CssBaseline } from '@mui/material';
const theme = createTheme({
  palette: { primary: { main: '#24584f' }, background: { default: '#f5f5f0', paper: '#ffffff' } },
  typography: { fontFamily: '"Segoe UI", "Microsoft JhengHei", sans-serif', button: { textTransform: 'none', fontWeight: 600 } },
  shape: { borderRadius: 10 },
  components: { MuiTextField: { defaultProps: { variant: 'outlined', size: 'small', fullWidth: true } }, MuiButton: { defaultProps: { disableElevation: true } } },
});
export default function Theme({ children }: { children: React.ReactNode }) {
  return <ThemeProvider theme={theme}><CssBaseline />{children}</ThemeProvider>;
}
