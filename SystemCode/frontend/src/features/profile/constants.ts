import type { MessageKey } from "../../i18n/en";
import type { JobSearchConstraints, ResumeDocument, UserProfile } from "../../types/api";

export type ListKey = "experiences" | "projects" | "research" | "educations" | "certificates" | "skill_groups" | "awards";
export type Option = readonly [value: string, labelKey: MessageKey];

// 必填项未完成时的提示色：首次保存前为琥珀色，点过保存后转为红色
export const TODO_AMBER = "#8a6a3b";
export const ERROR_RED = "#9d3a2c";
export const MONTH_PATTERN = /^\d{4}-\d{2}$/;

export const EMPTY_CONSTRAINTS: JobSearchConstraints = {
  target_roles: [], target_industries: [], work_modes: [],
  target_employment_types: [], notes: "",
};

const EMPTY_EDUCATION = { institution: "", entry_type: "degree", degree: "not_applicable", major: "", start_date: "", end_date: "", country: "", school_tier: "", research_direction: "", gpa: "", ranking: "", courses: [] } as const;

export const EMPTY_RESUME: ResumeDocument = {
  name: "", email: "", phone: "", experiences: [], projects: [], research: [],
  skills: [], skill_groups: [],
  educations: [{ ...EMPTY_EDUCATION, courses: [] }],
  certificates: [], languages: [], awards: [], additional_info: [],
};

export const NEW_ITEMS: Record<ListKey, Record<string, unknown>> = {
  experiences: { company: "", title: "", employment_type: null, start_date: "", end_date: "", description: "", country: "" },
  projects: { title: "", summary: "", technologies: [], role: "", start_date: "", end_date: "" },
  research: { type: "research_project", title: "", institution: "", summary: "", start_date: "", end_date: "" },
  educations: { ...EMPTY_EDUCATION, courses: [] },
  certificates: { name: "", issuer: "", issue_date: "", expiry_date: "", score: "" },
  skill_groups: { category: "", description: "" },
  awards: { name: "", date: "" },
};

// 没有已保存画像时的初始草稿（深拷贝，避免改到常量）
export function emptyProfile(): UserProfile {
  return { resume: { ...EMPTY_RESUME, educations: EMPTY_RESUME.educations.map((item) => ({ ...item, courses: [] })) }, constraints: { ...EMPTY_CONSTRAINTS }, resume_upload_id: null };
}

export const DEGREE_OPTIONS: Option[] = [
  ["bachelor", "profile.degree.bachelor"], ["master", "profile.degree.master"], ["phd", "profile.degree.phd"],
  ["diploma", "profile.degree.diploma"], ["not_applicable", "profile.degree.notApplicable"],
];
export const ENTRY_TYPE_OPTIONS: Option[] = [["degree", "profile.entryType.degree"], ["exchange", "profile.entryType.exchange"]];
export const EMPLOYMENT_OPTIONS: Option[] = [
  ["full_time", "common.employment.fullTime"], ["part_time", "common.employment.partTime"], ["internship", "common.employment.internship"],
];
export const TARGET_EMPLOYMENT_OPTIONS: Option[] = [["full_time", "common.employment.fullTime"], ["internship", "common.employment.internship"]];
export const WORK_MODE_OPTIONS: Option[] = [["onsite", "profile.workMode.onsite"], ["hybrid", "profile.workMode.hybrid"], ["remote", "profile.workMode.remote"]];
export const RESEARCH_TYPE_OPTIONS: Option[] = [
  ["paper", "profile.researchType.paper"], ["patent", "profile.researchType.patent"], ["software_copyright", "profile.researchType.softwareCopyright"],
  ["thesis", "profile.researchType.thesis"], ["research_project", "profile.researchType.researchProject"], ["other", "profile.researchType.other"],
];
// 语言名作为数据提交，保持英文；面向新加坡学生，常用项含四大官方语言和最常见的几种华人方言
export const QUICK_LANGUAGES = ["English", "Mandarin", "Malay", "Tamil", "Hokkien", "Teochew", "Cantonese", "Hakka"];

// 国家/地区和语言的可搜索下拉选项（datalist）；作为数据提交，保持英文。仍允许填列表外的值，兼容简历解析出的写法
export const COUNTRIES = [
  "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
  "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan",
  "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cambodia", "Cameroon",
  "Canada", "Cape Verde", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo", "Costa Rica",
  "Croatia", "Cuba", "Cyprus", "Czech Republic", "Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador",
  "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France",
  "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau",
  "Guyana", "Haiti", "Honduras", "Hong Kong", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq",
  "Ireland", "Israel", "Italy", "Ivory Coast", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati",
  "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania",
  "Luxembourg", "Macau", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania",
  "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar",
  "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia",
  "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines",
  "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa",
  "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
  "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden",
  "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago",
  "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay",
  "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
];

// 含新加坡常见的华人方言（福建、潮州、广东、客家、海南、福州、兴化、上海）和马来、印度裔社群语言
export const LANGUAGES = [
  "Afrikaans", "Arabic", "Bengali", "Boyanese", "Bulgarian", "Burmese", "Cantonese", "Catalan", "Croatian", "Czech",
  "Danish", "Dutch", "English", "Estonian", "Filipino", "Finnish", "Foochow", "French", "German", "Greek",
  "Gujarati", "Hainanese", "Hakka", "Hebrew", "Henghua", "Hindi", "Hokkien", "Hungarian", "Icelandic", "Indonesian",
  "Irish", "Italian", "Japanese", "Javanese", "Kannada", "Kazakh", "Khmer", "Korean", "Lao", "Latvian",
  "Lithuanian", "Malay", "Malayalam", "Mandarin", "Marathi", "Mongolian", "Nepali", "Norwegian", "Persian", "Polish",
  "Portuguese", "Punjabi", "Romanian", "Russian", "Serbian", "Shanghainese", "Sindhi", "Sinhala", "Slovak", "Slovenian",
  "Spanish", "Swahili", "Swedish", "Tamil", "Telugu", "Teochew", "Thai", "Tibetan", "Turkish", "Ukrainian",
  "Urdu", "Uyghur", "Uzbek", "Vietnamese", "Welsh",
];
