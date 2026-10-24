import "./globals.css";

export const metadata = {
  title: "Veritas Claims"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
