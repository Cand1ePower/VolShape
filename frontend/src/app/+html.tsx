import { ScrollViewStyleReset } from 'expo-router/html';
import { type PropsWithChildren } from 'react';

export default function RootHtml({ children }: PropsWithChildren) {
  return (
    <html lang="zh-CN">
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta name="color-scheme" content="dark" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover"
        />
        <ScrollViewStyleReset />
        <style>{`
          html, body {
            margin: 0;
            padding: 0;
            min-height: 100%;
            background: #0a0a0c;
            color: #ffffff;
          }
          body {
            overflow-x: hidden;
          }
          #root {
            min-height: 100vh;
            background: #0a0a0c;
          }
        `}</style>
      </head>
      <body>{children}</body>
    </html>
  );
}
