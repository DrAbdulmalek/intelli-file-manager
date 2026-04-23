import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "IntelliFile - إدارة الملفات الذكية",
  description: "تطبيق شامل لتصنيف وإدارة الملفات بالذكاء الاصطناعي - يدعم العربية، البحث الدلالي، حماية التطبيقات، والمعالجة متعددة الوسائط",
  keywords: ["IntelliFile", "تصنيف الملفات", "ذكاء اصطناعي", "إدارة الملفات", "مانجارو"],
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <body className="antialiased bg-slate-950 text-slate-100 min-h-screen">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
