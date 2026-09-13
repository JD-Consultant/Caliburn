import type { Metadata } from 'next';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v16-appRouter';
import Theme from './theme';
import './styles.css';

export const metadata: Metadata = { title: 'Caliburn · 我的職務說明書', description: '整理自己的真實工作，建立專屬職務說明書。' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-Hant"><body><AppRouterCacheProvider><Theme>{children}</Theme></AppRouterCacheProvider></body></html>;
}
