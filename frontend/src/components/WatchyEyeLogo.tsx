import React, { useState, useEffect } from 'react';

interface WatchyEyeLogoProps {
  size?: 'sm' | 'md' | 'lg';
  showText?: boolean;
  className?: string;
}

export const WatchyEyeLogo: React.FC<WatchyEyeLogoProps> = ({
  size = 'md',
  showText = true,
  className = '',
}) => {
  const [isBlinking, setIsBlinking] = useState(false);

  useEffect(() => {
    // Subtle blink every 4 to 6 seconds
    const interval = setInterval(() => {
      setIsBlinking(true);
      setTimeout(() => {
        setIsBlinking(false);
      }, 220); // blink duration
    }, 4500);

    return () => clearInterval(interval);
  }, []);

  const sizeClasses = {
    sm: 'w-7 h-7',
    md: 'w-9 h-9',
    lg: 'w-12 h-12',
  }[size];

  const textSizeClasses = {
    sm: 'text-base',
    md: 'text-xl',
    lg: 'text-2xl',
  }[size];

  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      <div
        className={`relative ${sizeClasses} rounded-xl bg-gradient-to-tr from-slate-900 via-indigo-950 to-slate-800 dark:from-indigo-950 dark:to-slate-900 border border-indigo-500/20 shadow-sm flex items-center justify-center overflow-hidden`}
        title="Watchy - Surveillance continue Google Maps"
      >
        {/* Radar ambient glow */}
        <div className="absolute inset-0 bg-radial from-emerald-500/20 to-transparent opacity-60" />

        {/* Eye SVG with blink animation */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`w-5 h-5 text-emerald-400 transition-transform duration-200 ${
            isBlinking ? 'scale-y-[0.1]' : 'scale-y-100'
          }`}
        >
          {/* Eye outline */}
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
          {/* Pupil */}
          <circle cx="12" cy="12" r="3" fill="#34d399" />
          {/* Iris glint */}
          <circle cx="13" cy="11" r="1" fill="#ffffff" />
        </svg>

        {/* Live micro-dot on top-right */}
        <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping opacity-75" />
      </div>

      {showText && (
        <div className="flex flex-col">
          <div className={`font-extrabold tracking-tight text-slate-900 dark:text-white ${textSizeClasses}`}>
            Watch<span className="text-emerald-600 dark:text-emerald-400">My</span>Business
          </div>
          <span className="text-[10px] font-medium uppercase tracking-wider text-slate-600 dark:text-slate-400 -mt-0.5">
            Avis clients · NLP maison
          </span>
        </div>
      )}
    </div>
  );
};
