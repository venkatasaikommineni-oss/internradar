import React from "react";
import { Compass, ExternalLink } from "lucide-react";

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-slate-200 bg-white mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded bg-blue-600 flex items-center justify-center text-white">
              <Compass className="h-3.5 w-3.5" />
            </div>
            <span className="font-semibold text-slate-900 text-sm tracking-tight">InternRadar</span>
            <span className="text-slate-300 mx-1">·</span>
            <span className="text-xs text-slate-500">Internship directory for students across India</span>
          </div>

          <div className="flex items-center gap-5 text-xs text-slate-500">
            <a href="#discover" className="hover:text-slate-900 transition-colors">
              Internships
            </a>
            <a href="#matches" className="hover:text-slate-900 transition-colors">
              Matches
            </a>
            <a
              href="/api/docs"
              target="_blank"
              rel="noreferrer"
              className="hover:text-slate-900 transition-colors flex items-center gap-1"
            >
              API Docs <ExternalLink className="h-3 w-3" />
            </a>
            <span className="text-slate-300">·</span>
            <span>&copy; {new Date().getFullYear()}</span>
          </div>
        </div>
      </div>
    </footer>
  );
};
