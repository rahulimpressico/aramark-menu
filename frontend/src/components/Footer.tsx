import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { AramarkLogo } from './AramarkLogo';

const linkColumns = [
  {
    title: null,
    links: [
      { label: 'About Aramark', to: '/about-us', external: false },
      { label: 'Home', to: '/', external: false },
      { label: 'Contact Us', to: 'https://www.aramark.com/contact-us', external: true },
    ],
  },
  {
    title: null,
    links: [
      { label: 'Careers', to: 'https://careers.aramark.com/', external: true },
      { label: 'Why Us', to: 'https://careers.aramark.com/why-us/', external: true },
    ],
  },
  {
    title: null,
    links: [
      { label: 'Newsroom', to: '/newsroom', external: false },
      { label: 'Investor Relations', to: 'https://aramark.gcs-web.com/', external: true },
      { label: 'Latest News', to: '/newsroom/news', external: false },
      { label: 'Media Kit', to: '/newsroom/media-kit', external: false },
      { label: 'Corporate Blog', to: '/newsroom/blog', external: false },
    ],
  },
  {
    title: 'For Employees',
    links: [
      { label: 'MyPay', to: '/mypayinfo', external: false },
    ],
  },
];

const socialLinks = [
  { label: "Aramark's YouTube", url: 'https://www.youtube.com/user/aramarktv', icon: 'youtube' },
  { label: "Aramark's LinkedIn", url: 'https://www.linkedin.com/company/aramark', icon: 'linkedin' },
  { label: "Aramark's Facebook", url: 'https://www.facebook.com/Aramark', icon: 'facebook' },
  { label: "Aramark's Twitter", url: 'https://twitter.com/Aramark', icon: 'twitter' },
  { label: "Aramark's Instagram", url: 'https://www.instagram.com/aramark/', icon: 'instagram' },
];

const legalLinks = [
  { label: 'Terms & Conditions', to: '/terms-conditions', external: false },
  { label: 'Privacy Policy', to: '/privacy-policy', external: false },
  { label: 'Do Not Sell Or Share My Personal Information', to: '/privacy-policy/consumer-request', external: false },
  { label: 'Help Center', to: 'https://www.aramark.com/contact-us', external: true },
];

function SocialIcon({ name }: { name: string }) {
  const size = 24;
  switch (name) {
    case 'youtube':
      return (
        <svg width={size} height={Math.round(size * 17 / 24)} viewBox="0 0 24 17" fill="currentColor" aria-hidden>
          <path d="M23.8 3.6C23.8 3.6 23.6 1.9 22.8 1.2C21.9 0.2 20.9 0.2 20.4 0.2C17 0 12 0 12 0C12 0 7 0 3.6 0.2C3.1 0.3 2.1 0.3 1.2 1.2C0.5 1.9 0.2 3.6 0.2 3.6C0.2 3.6 0 5.5 0 7.5V9.3C0 11.2 0.2 13.2 0.2 13.2C0.2 13.2 0.4 14.9 1.2 15.6C2.1 16.6 3.3 16.5 3.8 16.6C5.7 16.8 12 16.8 12 16.8C12 16.8 17 16.8 20.4 16.5C20.9 16.4 21.9 16.4 22.8 15.5C23.5 14.8 23.8 13.1 23.8 13.1C23.8 13.1 24 11.2 24 9.2V7.4C24 5.5 23.8 3.6 23.8 3.6ZM9.5 11.5V4.8L16 8.2L9.5 11.5Z" />
        </svg>
      );
    case 'linkedin':
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
          <path d="M23 0H1C0.4 0 0 0.4 0 1V23C0 23.6 0.4 24 1 24H23C23.6 24 24 23.6 24 23V1C24 0.4 23.6 0 23 0ZM7.1 20.5H3.6V9H7.2V20.5H7.1ZM5.3 7.4C4.2 7.4 3.2 6.5 3.2 5.3C3.2 4.2 4.1 3.2 5.3 3.2C6.4 3.2 7.4 4.1 7.4 5.3C7.4 6.5 6.5 7.4 5.3 7.4ZM20.5 20.5H16.9V14.9C16.9 13.6 16.9 11.9 15.1 11.9C13.2 11.9 13 13.3 13 14.8V20.5H9.4V9H12.8V10.6C13.3 9.7 14.4 8.8 16.2 8.8C19.8 8.8 20.5 11.2 20.5 14.3V20.5Z" />
        </svg>
      );
    case 'facebook':
      return (
        <svg width={Math.round(size * 10 / 24)} height={size} viewBox="0 0 10 20" fill="currentColor" aria-hidden>
          <path d="M8.11163 3.29509H9.92331V0.139742C9.61075 0.0967442 8.53581 0 7.28393 0C4.67183 0 2.88248 1.643 2.88248 4.66274V7.44186H0V10.9693H2.88248V19.845H6.41654V10.9701H9.18243L9.6215 7.44269H6.41571V5.01251C6.41654 3.99297 6.69106 3.29509 8.11163 3.29509Z" />
        </svg>
      );
    case 'twitter':
      return (
        <svg width={size} height={size} viewBox="0 0 20 20.45" fill="currentColor" aria-hidden>
          <path d="M11.903 8.655 19.348 0h-1.764L11.119 7.515 5.955 0H0l7.808 11.364L0 20.439h1.764l6.827 -7.936 5.453 7.936H20L11.902 8.655zM9.486 11.464l-0.791 -1.132 -6.295 -9.004h2.71l5.08 7.267 0.791 1.132 6.603 9.445H14.875L9.486 11.464z" />
        </svg>
      );
    case 'instagram':
      return (
        <svg width={size} height={size} viewBox="0 0 22 22" fill="currentColor" aria-hidden>
          <path fillRule="evenodd" clipRule="evenodd" d="M6.875 0H15.125C18.9214 0 22 3.07862 22 6.875V15.125C22 18.9214 18.9214 22 15.125 22H6.875C3.07862 22 0 18.9214 0 15.125V6.875C0 3.07862 3.07862 0 6.875 0ZM15.125 19.9375C17.7787 19.9375 19.9375 17.7787 19.9375 15.125V6.875C19.9375 4.22125 17.7787 2.0625 15.125 2.0625H6.875C4.22125 2.0625 2.0625 4.22125 2.0625 6.875V15.125C2.0625 17.7787 4.22125 19.9375 6.875 19.9375H15.125Z" />
          <path fillRule="evenodd" clipRule="evenodd" d="M5.5 11C5.5 7.96263 7.96263 5.5 11 5.5C14.0374 5.5 16.5 7.96263 16.5 11C16.5 14.0374 14.0374 16.5 11 16.5C7.96263 16.5 5.5 14.0374 5.5 11ZM7.5625 11C7.5625 12.8948 9.10525 14.4375 11 14.4375C12.8948 14.4375 14.4375 12.8948 14.4375 11C14.4375 9.10388 12.8948 7.5625 11 7.5625C9.10525 7.5625 7.5625 9.10388 7.5625 11Z" />
          <circle cx="16.9125" cy="5.08749" r="0.732875" />
        </svg>
      );
    default:
      return null;
  }
}

export function Footer() {
  const [email, setEmail] = useState('');

  function handleNewsletterSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!email.trim()) return;
    setEmail('');
  }

  return (
    <footer className="bg-footer-bg text-gray-200 mt-auto border-t border-white/5" role="contentinfo">
      <div className="max-w-[1200px] mx-auto px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-2.5 border-b border-white/10">
          <Link to="/" className="inline-block text-inherit no-underline hover:opacity-90 focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2" title="Aramark Logo">
            <AramarkLogo variant="white" width={120} height={30} />
            <span className="sr-only">Aramark home page</span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-[0.75rem] font-medium text-white/90">Ready to get started?</span>
            <a
              href="https://www.aramark.com/contact-us"
              className="inline-flex items-center px-2.5 py-1 text-[0.75rem] font-semibold text-white bg-primary rounded no-underline w-fit cursor-pointer hover:bg-primary-hover transition-colors focus-visible:outline-2 focus-visible:outline-white focus-visible:outline-offset-2"
              target="_blank"
              rel="noopener noreferrer"
            >
              Contact Us
            </a>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[0.6875rem] text-white/70 whitespace-nowrap">News Alerts</span>
            <form className="flex gap-1.5" onSubmit={handleNewsletterSubmit} noValidate>
              <label htmlFor="footer-newsletter-email" className="sr-only">Email</label>
              <input
                id="footer-newsletter-email"
                type="email"
                className="w-[120px] px-2 py-0.5 text-[0.75rem] text-gray-900 bg-white/95 border border-white/20 rounded placeholder:text-gray-500 focus:border-primary focus:outline-none"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
              <button type="submit" className="inline-flex items-center justify-center w-7 h-6 bg-primary rounded text-white text-[0.75rem] cursor-pointer hover:bg-primary-hover" aria-label="Subscribe">→</button>
            </form>
          </div>
        </div>

        <nav className="flex flex-wrap gap-x-5 gap-y-1.5 py-2 text-[0.75rem]" aria-label="Footer navigation">
          {linkColumns.map((col, i) => (
            <div key={i} className="flex flex-wrap items-center gap-x-3 gap-y-1">
              {col.title && <span className="text-[0.75rem] font-semibold text-white/90 mr-1">{col.title}</span>}
              <ul className="list-none m-0 p-0 flex flex-wrap gap-x-3 gap-y-1">
                {col.links.map((link) => (
                  <li key={link.label} className="m-0">
                    {link.external ? (
                      <a href={link.to} className="text-[0.75rem] text-white/80 no-underline hover:text-white transition-colors focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2" target="_blank" rel="noopener noreferrer">{link.label}</a>
                    ) : (
                      <Link to={link.to} className="text-[0.75rem] text-white/80 no-underline hover:text-white transition-colors">{link.label}</Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/10">
          <div className="flex items-center gap-1.5" aria-label="Social media">
            {socialLinks.map((s) => (
              <a
                key={s.icon}
                href={s.url}
                className="inline-flex items-center justify-center text-white/85 no-underline hover:text-white transition-opacity focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2"
                target="_blank"
                rel="noopener noreferrer"
                title={s.label}
              >
                <SocialIcon name={s.icon} />
              </a>
            ))}
          </div>
          <ul className="flex flex-wrap gap-x-3 gap-y-1 list-none m-0 p-0 text-[0.6875rem]">
            {legalLinks.map((link) => (
              <li key={link.label}>
                {link.external ? (
                  <a href={link.to} className="text-[0.6875rem] text-white/60 no-underline hover:text-white/90" target="_blank" rel="noopener noreferrer">
                    {link.label}
                  </a>
                ) : (
                  <Link to={link.to} className="text-[0.6875rem] text-white/60 no-underline hover:text-white/90">
                    {link.label}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  );
}
