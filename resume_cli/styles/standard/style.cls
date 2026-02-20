\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume}[2026/01/03 Custom AWS Architect Resume Class]

\LoadClass[a4paper,9pt]{extarticle} % Use extarticle for 9pt support

% Essential Packages
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage[left=2.5cm, right=2.5cm, top=2cm, bottom=2cm]{geometry}
\RequirePackage{titlesec}
\RequirePackage{enumitem}
\RequirePackage{hyperref}
\RequirePackage{xcolor}
\RequirePackage{fontawesome5}
\RequirePackage[scaled]{helvet}
\RequirePackage{array}
\RequirePackage[table]{xcolor}
\RequirePackage{fontawesome5}
\RequirePackage{graphicx}
\RequirePackage{multirow}
\RequirePackage{calc}
\renewcommand{\familydefault}{\sfdefault}
\renewcommand{\watermarkopacity}{0.2}

% Styles
\definecolor{accent}{HTML}{000000}
\definecolor{skillblue}{HTML}{dae8fe}

\hypersetup{colorlinks=true, linkcolor=accent, urlcolor=accent}

\titleformat{\section}{\large\bfseries\color{accent}}{}{0em}{}[]
\titlespacing*{\section}{0pt}{12pt}{8pt}

% --- CUSTOM COMMANDS ---

% Header Command: \resumeHeader{Name}{Title}{Location}{Email}{Phone}{LinkedIn}{GitHub}{Twitter}
\newcommand{\resumeHeader}[8]{
    \begin{center}
        {\Huge \textbf{\color{accent} #1}} \\
        \vspace{4pt}
        \textbf{#2} \\
        #3 | \href{mailto:#4}{#4} | #5 \\
        \href{#6}{LinkedIn} | \href{#7}{GitHub}
    \end{center}
}

% Experience Command: \role{Company}{Duration}{Position}{Location}
\newcommand{\role}[4]{%  <-- Add the % here to eat the newline
\textbf{#1(#4)} - {#2}\\
\textit{#3}%
\vspace{2pt}%
}

\newcommand{\jobdetail}[2][gray]{%
    \mbox{}\textcolor{#1}{\small\textbf{#2}}%
}


% Settings
\pagenumbering{gobble}
\setlist[itemize]{leftmargin=1.5em, nosep, topsep=2pt}

\graphicspath{ {../../assets/img/logos/}{../../assets/img/badges/} }

% Remove indentation
\setlength{\parindent}{0pt}