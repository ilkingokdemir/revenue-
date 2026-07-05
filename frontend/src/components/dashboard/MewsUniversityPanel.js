/**
 * Mews University — In-app E-learning Panel (iter 364)
 * ------------------------------------------------------
 * Course catalog + course player (lesson list, markdown reader, inline quiz).
 * Renders inside the main dashboard.  Managers see leaderboard, staff see
 * "My Progress" hero.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  GraduationCap, PlayCircle, CheckCircle2, Clock, Award, Loader2,
  ArrowLeft, Sparkles, Trophy, Users, Circle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATEGORY_COLORS = {
  Reception:    "bg-sky-500/10 text-sky-300 border-sky-500/30",
  Housekeeping: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  Revenue:      "bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/30",
  Experience:   "bg-amber-500/10 text-amber-300 border-amber-500/30",
  Safety:       "bg-rose-500/10 text-rose-300 border-rose-500/30",
  Technology:   "bg-indigo-500/10 text-indigo-300 border-indigo-500/30",
};

const LEVEL_LABELS = {
  beginner:     "Başlangıç",
  intermediate: "Orta",
  advanced:     "İleri",
};

export default function MewsUniversityPanel({ userRole = "" }) {
  const [courses, setCourses] = useState([]);
  const [me, setMe] = useState(null);
  const [leaderboard, setLeaderboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState("");

  const isManager = ["admin", "manager"].includes((userRole || "").toLowerCase());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, m, lb] = await Promise.all([
        axios.get(`${API}/university/courses`),
        axios.get(`${API}/university/me`),
        isManager ? axios.get(`${API}/university/leaderboard`) : Promise.resolve({ data: null }),
      ]);
      setCourses(c.data.items || []);
      setMe(m.data);
      setLeaderboard(lb.data);
    } catch {
      toast.error("University yüklenemedi");
    }
    setLoading(false);
  }, [isManager]);

  useEffect(() => { load(); }, [load]);

  const seedCourses = async () => {
    if (!window.confirm("6 varsayılan kurs (28 ders) yüklensin mi? Tekrar çalıştırılırsa çoğaltmaz.")) return;
    try {
      const r = await axios.post(`${API}/university/courses/seed`);
      toast.success(`${r.data.courses_created} kurs · ${r.data.lessons_created} ders yüklendi`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Seed başarısız");
    }
  };

  const openCourse = async (courseId) => {
    try {
      await axios.post(`${API}/university/courses/${courseId}/enroll`).catch(() => {});
      const r = await axios.get(`${API}/university/courses/${courseId}`);
      setSelectedCourse(r.data);
    } catch {
      toast.error("Kurs açılamadı");
    }
  };

  const filteredCourses = categoryFilter
    ? courses.filter((c) => c.category === categoryFilter)
    : courses;

  const categories = [...new Set(courses.map((c) => c.category))];

  if (selectedCourse) {
    return (
      <CoursePlayer
        course={selectedCourse}
        onBack={() => { setSelectedCourse(null); load(); }}
        onLessonComplete={async (lessonId) => {
          await axios.put(`${API}/university/lessons/${lessonId}/complete`);
          const r = await axios.get(`${API}/university/courses/${selectedCourse.id}`);
          setSelectedCourse(r.data);
        }}
        onQuizSubmit={async (lessonId, answerIndex) => {
          const r = await axios.post(`${API}/university/lessons/${lessonId}/quiz`, { answer_index: answerIndex });
          const detail = await axios.get(`${API}/university/courses/${selectedCourse.id}`);
          setSelectedCourse(detail.data);
          return r.data;
        }}
      />
    );
  }

  return (
    <div className="space-y-6" data-testid="mews-university-panel">
      {/* Hero */}
      <div className="rounded-2xl border border-indigo-500/30 bg-gradient-to-br from-indigo-600/10 via-fuchsia-600/5 to-transparent p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-3 pr-4 border-r border-white/10">
              <img src="/logos/myhotelbox_icon.png" alt="MyHotelBox" className="w-11 h-11 rounded-xl shadow-lg" />
              <img src="/logos/reveniq_icon.png" alt="ReveniQ" className="w-11 h-11 rounded-xl shadow-lg" />
            </div>
            <div className="p-3 rounded-xl bg-indigo-500/20 md:hidden">
              <GraduationCap className="w-7 h-7 text-indigo-300" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-stone-100">HotelBox Academy</h2>
              <p className="text-sm text-stone-400">MyHotelBox &amp; ReveniQ ekibin için self-training — SOP, RM, safety, PMS ve daha fazlası</p>
            </div>
          </div>
          {isManager && courses.length === 0 && (
            <button
              onClick={seedCourses}
              data-testid="mu-seed-btn"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm"
            >
              <Sparkles className="w-4 h-4" /> Varsayılan Kursları Yükle
            </button>
          )}
        </div>

        {/* My stats */}
        {me && (
          <div className="grid grid-cols-3 gap-3 mt-5" data-testid="mu-my-stats">
            <MetricPill icon={PlayCircle} label="Kayıtlı Kurs" value={me.total_enrolled} />
            <MetricPill icon={CheckCircle2} label="Tamamlanan" value={me.total_completed} />
            <MetricPill icon={Award} label="Toplam Ders" value={me.total_lessons_done} />
          </div>
        )}
      </div>

      {/* My in-progress */}
      {me?.items?.length > 0 && (
        <div>
          <h3 className="text-sm uppercase tracking-wider text-stone-400 mb-2">Devam Ettiklerin</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {me.items.slice(0, 3).map((e) => (
              <MyEnrollmentCard key={e.course_id} item={e} onOpen={() => openCourse(e.course_id)} />
            ))}
          </div>
        </div>
      )}

      {/* Catalog */}
      <div>
        <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
          <h3 className="text-sm uppercase tracking-wider text-stone-400">Katalog</h3>
          <div className="flex gap-1 flex-wrap">
            <button
              onClick={() => setCategoryFilter("")}
              className={`px-3 py-1 rounded-full text-xs border ${!categoryFilter
                ? "bg-stone-700 border-stone-600 text-stone-100"
                : "bg-transparent border-stone-700 text-stone-400 hover:bg-stone-800"}`}
              data-testid="mu-filter-all"
            >
              Tümü ({courses.length})
            </button>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-3 py-1 rounded-full text-xs border ${categoryFilter === cat
                  ? "bg-stone-700 border-stone-600 text-stone-100"
                  : "bg-transparent border-stone-700 text-stone-400 hover:bg-stone-800"}`}
                data-testid={`mu-filter-${cat}`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16 text-stone-500">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : filteredCourses.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-stone-700 rounded-xl">
            <GraduationCap className="w-12 h-12 text-stone-600 mx-auto mb-3" />
            <p className="text-stone-300 font-medium mb-2">Henüz kurs yok</p>
            {isManager && (
              <button
                onClick={seedCourses}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold"
                data-testid="mu-empty-seed-btn"
              >
                Varsayılan Kursları Yükle
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="mu-course-grid">
            {filteredCourses.map((c) => (
              <CourseCard key={c.id} course={c} onOpen={() => openCourse(c.id)} />
            ))}
          </div>
        )}
      </div>

      {/* Leaderboard (managers only) */}
      {isManager && leaderboard?.items?.length > 0 && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-5" data-testid="mu-leaderboard">
          <div className="flex items-center gap-2 mb-3">
            <Trophy className="w-5 h-5 text-amber-400" />
            <h3 className="text-lg font-semibold text-stone-100">Top Learners · Son 30 Gün</h3>
          </div>
          <div className="space-y-1">
            {leaderboard.items.map((u, idx) => (
              <div key={u.user_email} className="flex items-center justify-between px-3 py-2 rounded-lg bg-stone-800/40">
                <div className="flex items-center gap-3">
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-black ${
                    idx === 0 ? "bg-amber-500/20 text-amber-300" :
                    idx === 1 ? "bg-stone-500/30 text-stone-200" :
                    idx === 2 ? "bg-orange-700/30 text-orange-300" :
                    "bg-stone-800 text-stone-400"
                  }`}>{idx + 1}</span>
                  <span className="text-sm text-stone-200">{u.user_email}</span>
                </div>
                <div className="flex items-center gap-3 text-xs">
                  <span className="text-stone-400">{u.lessons_done} ders</span>
                  <span className="text-emerald-300 font-semibold">Quiz ort. {u.avg_quiz_score}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricPill({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl bg-stone-800/60 border border-stone-800">
      <Icon className="w-5 h-5 text-indigo-300" />
      <div>
        <div className="text-[10px] uppercase tracking-wider text-stone-400">{label}</div>
        <div className="text-xl font-bold text-stone-100">{value}</div>
      </div>
    </div>
  );
}

function CourseCard({ course, onOpen }) {
  const catCls = CATEGORY_COLORS[course.category] || "bg-stone-700 text-stone-200 border-stone-600";
  const done = course.progress_pct === 100;
  return (
    <button
      onClick={onOpen}
      data-testid="mu-course-card"
      className="text-left rounded-xl border border-stone-800 bg-stone-900/60 hover:bg-stone-900 hover:border-indigo-500/40 transition overflow-hidden group"
    >
      <div className="relative h-32 overflow-hidden">
        <img
          src={course.thumbnail}
          alt={course.title}
          className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
          loading="lazy"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-stone-900 via-transparent to-transparent" />
        {course.is_mandatory && (
          <span className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-rose-500/90 text-white text-[10px] font-bold uppercase">
            Zorunlu
          </span>
        )}
        {done && (
          <div className="absolute top-2 left-2 p-1 rounded-full bg-emerald-500 text-white">
            <CheckCircle2 className="w-4 h-4" />
          </div>
        )}
      </div>
      <div className="p-4 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase border ${catCls}`}>
            {course.category}
          </span>
          <span className="text-[10px] text-stone-500 uppercase">{LEVEL_LABELS[course.level] || course.level}</span>
        </div>
        <div className="text-stone-100 font-semibold leading-tight">{course.title}</div>
        <div className="text-xs text-stone-400 line-clamp-2">{course.description}</div>
        <div className="flex items-center justify-between text-xs text-stone-500">
          <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {course.duration_min} dk</span>
          <span>{course.completed_lessons}/{course.lesson_count} ders</span>
        </div>
        <div className="h-1.5 bg-stone-800 rounded overflow-hidden">
          <div className={`h-full ${done ? "bg-emerald-500" : "bg-indigo-500"}`} style={{ width: `${course.progress_pct}%` }} />
        </div>
      </div>
    </button>
  );
}

function MyEnrollmentCard({ item, onOpen }) {
  const done = item.progress_pct === 100;
  return (
    <button
      onClick={onOpen}
      data-testid="mu-my-card"
      className="text-left flex items-center gap-3 p-3 rounded-xl bg-stone-800/50 border border-stone-800 hover:border-indigo-500/40 transition"
    >
      <img src={item.thumbnail} alt="" className="w-16 h-16 rounded-lg object-cover" loading="lazy" />
      <div className="flex-1 min-w-0">
        <div className="text-stone-100 font-semibold truncate">{item.title}</div>
        <div className="text-[10px] text-stone-400 uppercase mb-1">{item.category}</div>
        <div className="h-1.5 bg-stone-900 rounded overflow-hidden">
          <div className={`h-full ${done ? "bg-emerald-500" : "bg-indigo-500"}`} style={{ width: `${item.progress_pct}%` }} />
        </div>
        <div className="text-[11px] text-stone-500 mt-1">{item.completed_lessons}/{item.lesson_count} · {item.progress_pct}%</div>
      </div>
      {done && <Award className="w-6 h-6 text-emerald-400" />}
    </button>
  );
}

// ────────────────────────────────────────────────────────────────
// CoursePlayer — lesson list + markdown reader + inline quiz
// ────────────────────────────────────────────────────────────────
function CoursePlayer({ course, onBack, onLessonComplete, onQuizSubmit }) {
  const [activeLessonIdx, setActiveLessonIdx] = useState(() => {
    const firstIncomplete = course.lessons.findIndex((l) => !l.completed);
    return firstIncomplete >= 0 ? firstIncomplete : 0;
  });
  const [quizChoice, setQuizChoice] = useState(null);
  const [quizResult, setQuizResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const lesson = course.lessons[activeLessonIdx];

  useEffect(() => {
    setQuizChoice(null);
    setQuizResult(lesson?.quiz_score != null ? {
      passed: lesson.quiz_score === 100,
      score: lesson.quiz_score,
      already_taken: true,
    } : null);
  }, [activeLessonIdx, lesson?.quiz_score]);

  const markComplete = async () => {
    setSubmitting(true);
    try {
      await onLessonComplete(lesson.id);
      toast.success("Ders tamamlandı");
      if (activeLessonIdx < course.lessons.length - 1) {
        setActiveLessonIdx(activeLessonIdx + 1);
      }
    } catch { toast.error("Kaydedilemedi"); }
    setSubmitting(false);
  };

  const submitQuiz = async () => {
    if (quizChoice == null) { toast.error("Bir seçenek seçin"); return; }
    setSubmitting(true);
    try {
      const r = await onQuizSubmit(lesson.id, quizChoice);
      setQuizResult(r);
      if (r.passed) toast.success("Doğru! Tebrikler 🎉");
      else toast.error("Yanlış cevap. Tekrar deneyebilirsiniz.");
    } catch { toast.error("Gönderilemedi"); }
    setSubmitting(false);
  };

  const done = course.progress_pct === 100;

  return (
    <div className="space-y-4" data-testid="mu-course-player">
      <div className="flex items-center gap-3">
        <button onClick={onBack} data-testid="mu-back-btn"
          className="p-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="text-xl font-bold text-stone-100 truncate">{course.title}</h2>
          <div className="flex items-center gap-3 text-xs text-stone-400">
            <span className="flex items-center gap-1"><Users className="w-3 h-3" />{course.category}</span>
            <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{course.duration_min} dk</span>
            <span>{course.progress_pct}% tamamlandı</span>
          </div>
        </div>
        {done && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-bold">
            <Award className="w-4 h-4" /> Sertifika kazanıldı
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px,1fr] gap-4">
        {/* Lesson list */}
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-2 space-y-1 lg:sticky lg:top-4 lg:self-start" data-testid="mu-lesson-list">
          {course.lessons.map((l, idx) => {
            const active = idx === activeLessonIdx;
            return (
              <button
                key={l.id}
                onClick={() => setActiveLessonIdx(idx)}
                data-testid={`mu-lesson-${idx}`}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left text-sm ${
                  active ? "bg-indigo-500/20 border border-indigo-500/40 text-indigo-100"
                          : "hover:bg-stone-800 text-stone-300 border border-transparent"
                }`}
              >
                {l.completed
                  ? <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  : <Circle className="w-4 h-4 text-stone-600 flex-shrink-0" />}
                <span className="flex-1 truncate">{idx + 1}. {l.title}</span>
                {l.quiz && <Sparkles className="w-3 h-3 text-amber-400 flex-shrink-0" />}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-6 min-h-[400px]" data-testid="mu-lesson-content">
          <MarkdownLite text={lesson.content_md} />

          {lesson.quiz && (
            <div className="mt-6 pt-6 border-t border-stone-800 space-y-3" data-testid="mu-quiz-area">
              <div className="flex items-center gap-2 text-amber-300 text-sm font-semibold">
                <Sparkles className="w-4 h-4" /> Quiz
              </div>
              <div className="text-stone-100 font-medium">{lesson.quiz.question}</div>
              <div className="space-y-2">
                {lesson.quiz.options.map((opt, idx) => {
                  const isCorrect = quizResult && quizResult.correct_index === idx;
                  const isChosen = quizChoice === idx;
                  const showFeedback = !!quizResult && !quizResult.already_taken;
                  return (
                    <button
                      key={idx}
                      onClick={() => !quizResult && setQuizChoice(idx)}
                      disabled={!!quizResult && quizResult.already_taken}
                      data-testid={`mu-quiz-opt-${idx}`}
                      className={`w-full text-left px-4 py-2 rounded-lg border transition ${
                        showFeedback && isCorrect ? "bg-emerald-500/20 border-emerald-500/60 text-emerald-100" :
                        showFeedback && isChosen && !isCorrect ? "bg-rose-500/20 border-rose-500/60 text-rose-100" :
                        isChosen ? "bg-indigo-500/20 border-indigo-500/40 text-indigo-100" :
                        "bg-stone-800/60 border-stone-700 text-stone-200 hover:bg-stone-800"
                      }`}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>
              {!quizResult && (
                <button
                  onClick={submitQuiz}
                  disabled={quizChoice == null || submitting}
                  data-testid="mu-quiz-submit"
                  className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-black text-sm font-bold"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Cevabı Gönder"}
                </button>
              )}
              {quizResult && !quizResult.passed && !quizResult.already_taken && (
                <button
                  onClick={() => { setQuizResult(null); setQuizChoice(null); }}
                  className="px-4 py-2 rounded-lg bg-stone-700 hover:bg-stone-600 text-white text-sm font-bold"
                  data-testid="mu-quiz-retry"
                >
                  Tekrar Dene
                </button>
              )}
              {quizResult && quizResult.passed && (
                <div className="text-emerald-300 text-sm font-semibold flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" /> Doğru! Ders otomatik tamamlandı.
                </div>
              )}
            </div>
          )}

          {/* Mark complete for non-quiz lessons */}
          {!lesson.quiz && !lesson.completed && (
            <div className="mt-6 pt-6 border-t border-stone-800">
              <button
                onClick={markComplete}
                disabled={submitting}
                data-testid="mu-complete-btn"
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-bold"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                Dersi Tamamla
              </button>
            </div>
          )}
          {!lesson.quiz && lesson.completed && (
            <div className="mt-6 pt-6 border-t border-stone-800">
              <div className="text-emerald-300 text-sm font-semibold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" /> Bu ders tamamlandı
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Very small markdown renderer — supports headings (# ##), bold **x**, italic *x*,
 * bullets, numbered lists, code `x`, blockquotes and paragraphs. Kept dependency-free
 * so we don't pull marked/remark into the bundle for a single component.
 */
function MarkdownLite({ text }) {
  if (!text) return null;
  const lines = text.split("\n");
  const nodes = [];
  let inList = null;   // "ul" | "ol"
  let listItems = [];
  const flushList = () => {
    if (!inList) return;
    const Tag = inList === "ol" ? "ol" : "ul";
    nodes.push(
      <Tag key={`list-${nodes.length}`} className={`${inList === "ol" ? "list-decimal" : "list-disc"} pl-6 space-y-1 text-stone-200 text-sm`}>
        {listItems.map((li, i) => <li key={i} dangerouslySetInnerHTML={{ __html: inline(li) }} />)}
      </Tag>
    );
    inList = null; listItems = [];
  };
  const inline = (s) => s
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code class='px-1 py-0.5 rounded bg-stone-800 text-amber-300 text-[13px]'>$1</code>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");

  lines.forEach((line, i) => {
    if (/^\s*#\s+/.test(line)) {
      flushList();
      nodes.push(<h2 key={i} className="text-xl font-bold text-stone-100 mb-2">{line.replace(/^\s*#\s+/, "")}</h2>);
    } else if (/^\s*##\s+/.test(line)) {
      flushList();
      nodes.push(<h3 key={i} className="text-base font-bold text-indigo-300 mt-4 mb-2">{line.replace(/^\s*##\s+/, "")}</h3>);
    } else if (/^\s*>\s+/.test(line)) {
      flushList();
      nodes.push(<blockquote key={i} className="border-l-4 border-amber-500/50 pl-4 py-1 my-2 text-amber-200 text-sm italic" dangerouslySetInnerHTML={{ __html: inline(line.replace(/^\s*>\s+/, "")) }} />);
    } else if (/^\s*[-*]\s+/.test(line)) {
      if (inList !== "ul") { flushList(); inList = "ul"; }
      listItems.push(line.replace(/^\s*[-*]\s+/, ""));
    } else if (/^\s*\d+\.\s+/.test(line)) {
      if (inList !== "ol") { flushList(); inList = "ol"; }
      listItems.push(line.replace(/^\s*\d+\.\s+/, ""));
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      nodes.push(<p key={i} className="text-sm text-stone-300 leading-relaxed mb-2" dangerouslySetInnerHTML={{ __html: inline(line) }} />);
    }
  });
  flushList();
  return <div className="space-y-1">{nodes}</div>;
}
