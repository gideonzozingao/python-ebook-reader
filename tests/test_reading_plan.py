"""Reading plan: word counts, the no-overlap scheduler, progress and exports.

Run:  python -m pytest tests -q
No screen needed: everything here is Qt-free.
"""
import os
import tempfile
import zipfile

from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("EPUB_READER_HOME", tempfile.mkdtemp(prefix="br-test-"))

import pytest

from book_reader.services import plan_words as pw
from book_reader.services import reading_plan as rp
from book_reader.services.roadmap import Roadmap, RoadmapNode, generate_roadmap

MON = date(2026, 11, 2)   # a Monday


def words(n, word="lorem"):
    return " ".join([word] * n)


def flat_roadmap(*chapters, paged=False):
    """Roadmap with one level-1 entry per (title, words) and matching counts."""
    nodes = [RoadmapNode(t, 1, i, "", i + 1) for i, (t, _) in enumerate(chapters)]
    rm = Roadmap("Test", "pdf" if paged else "epub", len(nodes), "toc", nodes)
    counts = pw.WordCounts([w for _, w in chapters], sum(w for _, w in chapters), 0, False,
                           pw.roadmap_signature(rm))
    return rm, counts


def settings(**kw):
    base = dict(start=MON.isoformat(), minutes_per_day=30, weekdays=[0, 1, 2, 3, 4],
                wpm=230, study_factor=1.5, min_start=5)
    base.update(kw)
    return rp.PlanSettings(**base).clean()


# -- scheduler ---------------------------------------------------------------------------- #

def test_example_from_the_design():
    """Ch 1 = 21 min, Ch 2 = 35 min at 230 wpm x1.5, 30 min a weekday."""
    rm, counts = flat_roadmap(("Introduction", 3200), ("Foundations", 5367), ("Practice", 9000))
    s = settings()
    tasks = rp.build_tasks(rm, counts, s)
    assert [t.minutes for t in tasks[:2]] == [21, 35]
    sched = rp.schedule(tasks, s)
    day = sched.by_day()
    mon, tue = day[MON], day[MON + timedelta(days=1)]
    assert [(b.key, b.minutes, b.part, b.parts) for b in mon] == [
        (tasks[0].key, 21, 1, 1), (tasks[1].key, 9, 1, 2)]
    assert [(b.key, b.minutes, b.part) for b in tue] == [(tasks[1].key, 26, 2)]
    # 4 minutes left on Tuesday: not enough to start "Practice"
    assert sched.leftover[MON + timedelta(days=1)] == (4, "Practice")
    assert day[MON + timedelta(days=2)][0].key == tasks[2].key


def test_no_overlap_and_every_minute_once():
    rm, counts = flat_roadmap(*[(f"Ch {i}", 1000 + 777 * i) for i in range(1, 12)])
    s = settings(minutes_per_day=25, weekdays=[0, 2, 4, 5])
    tasks = rp.build_tasks(rm, counts, s)
    sched = rp.schedule(tasks, s)
    for d, blocks in sched.by_day().items():
        assert d.weekday() in s.weekdays
        pos = 0
        for b in blocks:                       # consecutive, never overlapping
            assert b.start_min == pos
            pos += b.minutes
        assert pos <= s.minutes_per_day
    for t in tasks:                            # each task scheduled exactly once in full
        assert sum(b.minutes for b in sched.blocks if b.key == t.key) == t.minutes
    order = [b.key for b in sched.blocks]      # tasks stay in book order
    assert sorted(set(order), key=order.index) == [t.key for t in tasks]


def test_short_task_still_fits_in_a_small_gap():
    rm, counts = flat_roadmap(("A", round(27 * 230 / 1.5)), ("B", round(2 * 230 / 1.5)))
    sched = rp.schedule(rp.build_tasks(rm, counts, settings(min_start=10)), settings(min_start=10))
    assert len(sched.days) == 1                # B (2 min) fits in the last 3 minutes


def test_skip_dates_and_weekdays():
    rm, counts = flat_roadmap(("A", 5000), ("B", 5000))
    s = settings(weekdays=[5, 6], skip_dates=["2026-11-07"])
    sched = rp.schedule(rp.build_tasks(rm, counts, s), s)
    assert sched.days[0] == date(2026, 11, 8)
    assert all(d.weekday() in (5, 6) for d in sched.days)


def test_no_weekdays_is_an_error():
    rm, counts = flat_roadmap(("A", 500))
    s = settings(weekdays=[])
    with pytest.raises(ValueError):
        rp.schedule(rp.build_tasks(rm, counts, s), s)


def test_work_backwards_from_a_finish_date():
    rm, counts = flat_roadmap(*[(f"Ch {i}", 6900) for i in range(9)])   # 62,100 words
    s = settings()
    tasks = rp.build_tasks(rm, counts, s)
    assert abs(sum(t.minutes for t in tasks) - 405) <= 9                # ≈ 6 h 45
    finish = MON + timedelta(days=18)                                   # Fri, week 3
    m = rp.minutes_needed(tasks, s, finish)
    assert m is not None
    s.minutes_per_day = m
    assert rp.schedule(tasks, s).finish <= finish
    s.minutes_per_day = m - 1
    assert rp.schedule(tasks, s).finish > finish                        # m is the least
    assert rp.minutes_needed(tasks, s, MON - timedelta(days=1)) is None


def test_review_and_mindmap_tasks_follow_each_chapter():
    nodes = [RoadmapNode("Ch 1", 1, 0, "", 1), RoadmapNode("1.1", 2, 0, "a", 1),
             RoadmapNode("1.2", 2, 1, "", 2), RoadmapNode("Ch 2", 1, 2, "", 3)]
    rm = Roadmap("T", "epub", 3, "toc", nodes)
    counts = pw.WordCounts([100, 2000, 3000, 4000], 9100, 0, False, pw.roadmap_signature(rm))
    s = settings(unit_level=2, review_minutes=10, mindmap_minutes=15)
    tasks = rp.build_tasks(rm, counts, s)
    # Ch 1's 100-word intro is too short for a task of its own: it joins 1.1
    assert [(t.kind, t.title) for t in tasks] == [
        ("read", "1.1"), ("read", "1.2"), ("review", "Ch 1"),
        ("mindmap", "Ch 1"), ("read", "Ch 2"), ("review", "Ch 2"), ("mindmap", "Ch 2")]
    assert tasks[0].words == 2100 and tasks[0].node == 0
    chapters = rp.build_tasks(rm, counts, settings(unit_level=1))
    assert [(t.title, t.words) for t in chapters] == [("Ch 1", 5100), ("Ch 2", 4000)]


def test_front_and_back_matter_is_left_out():
    rm, counts = flat_roadmap(("Cover", 815), ("Half Title", 180), ("Title Page", 50),
                              ("Copyright Page", 540), ("Contents", 900), ("Preface", 2000),
                              ("Part I", 40), ("Chapter 1", 6000), ("Index", 9000))
    s = settings(review_minutes=5, mindmap_minutes=10)
    tasks = rp.build_tasks(rm, counts, s)
    assert [(t.kind, t.title) for t in tasks] == [
        ("read", "Preface"), ("review", "Preface"), ("mindmap", "Preface"),
        ("read", "Chapter 1"), ("review", "Chapter 1"), ("mindmap", "Chapter 1")]
    assert tasks[3].words == 6040 and tasks[3].index == 6     # "Part I" folded in, opens there
    s.skip_matter = False
    assert len([t for t in rp.build_tasks(rm, counts, s) if t.kind == rp.READ]) == 7


def test_short_chapters_get_no_study_steps():
    rm, counts = flat_roadmap(("Foreword", 600), ("Chapter 1", 5000))
    tasks = rp.build_tasks(rm, counts, settings(review_minutes=5))
    assert [(t.kind, t.title) for t in tasks] == [
        ("read", "Foreword"), ("read", "Chapter 1"), ("review", "Chapter 1")]


# -- progress ------------------------------------------------------------------------------ #

def test_progress_status_and_replan():
    rm, counts = flat_roadmap(*[(f"Ch {i}", 4600) for i in range(6)])   # 30 min each
    plan = rp.ReadingPlan.new(MON, minutes_per_day=30, wpm=230, study_factor=1.5)
    tasks = rp.build_tasks(rm, counts, plan.settings)
    sched = rp.plan_schedule(plan, tasks)
    wed = MON + timedelta(days=2)
    st = rp.status(plan, tasks, sched, today=wed)
    assert st.behind_minutes == 60 and len(st.overdue) == 2 and st.today

    # reading past chapter 1 ticks it off automatically, never the other way round
    rp.auto_complete(plan, tasks, position=1, ratio=0.0, progress=0.2, today=MON)
    assert not plan.done                       # landing on chapter 2's first line is a jump
    rp.auto_complete(plan, tasks, position=1, ratio=0.3, progress=0.2, today=MON)
    assert list(plan.done) == [tasks[0].key]
    rp.auto_complete(plan, tasks, position=0, ratio=0.1, progress=0.0, today=wed)
    assert tasks[0].key in plan.done
    st = rp.status(plan, tasks, rp.plan_schedule(plan, tasks), today=wed)
    assert st.behind_minutes == 30

    rp.replan(plan, today=wed)
    sched = rp.plan_schedule(plan, tasks)
    assert sched.days[0] == wed
    assert tasks[0].key not in {b.key for b in sched.blocks}           # done before restart
    assert rp.status(plan, tasks, sched, today=wed).behind_minutes == 0

    again = rp.ReadingPlan.from_json(plan.to_json())
    assert again == plan


def test_jumping_ahead_does_not_tick_off_skipped_chapters():
    rm, counts = flat_roadmap(*[(f"Ch {i}", 2000) for i in range(6)])
    plan = rp.ReadingPlan.new(MON)
    tasks = rp.build_tasks(rm, counts, plan.settings)
    assert rp.auto_complete(plan, tasks, 4, 0.0, 0.66) == []          # a link: exact start
    # reading inside chapter 5 counts chapter 4 as read, never chapters 1-3
    assert rp.auto_complete(plan, tasks, 4, 0.5, 0.75) == [tasks[3].key]
    plan.done.clear()
    # reading on from chapter 1 into chapter 2 ticks off chapter 1 only
    assert rp.auto_complete(plan, tasks, 1, 0.2, 0.2) == [tasks[0].key]


def test_last_chapter_completes_at_the_end_of_the_book():
    rm, counts = flat_roadmap(("A", 1000), ("B", 1000))
    plan = rp.ReadingPlan.new(MON)
    tasks = rp.build_tasks(rm, counts, plan.settings)
    rp.auto_complete(plan, tasks, 1, 0.5, 0.75)
    assert tasks[1].key not in plan.done
    rp.auto_complete(plan, tasks, 1, 1.0, 0.99)
    assert tasks[1].key in plan.done


def test_personal_pace():
    assert rp.personal_wpm(1000, 3600) is None
    assert rp.personal_wpm(12000, 3600) == 200


# -- exports ------------------------------------------------------------------------------- #

def test_ics_and_markdown_export():
    rm, counts = flat_roadmap(("Introduction, the long one", 3200), ("Foundations", 5367))
    plan = rp.ReadingPlan.new(MON, minutes_per_day=30, study_factor=1.5)
    tasks = rp.build_tasks(rm, counts, plan.settings)
    sched = rp.plan_schedule(plan, tasks)
    ics = rp.build_ics(7, "My Book", plan, tasks, sched)
    assert ics.count("BEGIN:VEVENT") == len(sched.blocks) == 3
    assert "Introduction\\, the long one" in ics and ics.endswith("\r\n")
    assert all(len(line.encode()) <= 75 for line in ics.split("\r\n"))
    md = rp.build_markdown("My Book", plan, tasks, sched)
    assert "- [ ] Foundations, part 1 of 2 — 9 min" in md
    assert "## Mon 2 Nov 2026" in md


# -- word counts on real files ------------------------------------------------------------- #

def _epub(path: Path, chapters):
    """Minimal EPUB: chapters = [(title, [(section id, section title, words)])]."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml",
                   '<container><rootfiles><rootfile full-path="OEBPS/c.opf"/></rootfiles></container>')
        items, refs, nav = [], [], []
        for i, (title, sections) in enumerate(chapters):
            body = f"<h1>{title}</h1><p>{words(sections[0][2])}</p>"
            sub = []
            for sid, stitle, n in sections[1:]:
                body += f'<h2 id="{sid}">{stitle}</h2><p>{words(n)}</p>'
                sub.append(f'<li><a href="c{i}.xhtml#{sid}">{stitle}</a></li>')
            z.writestr(f"OEBPS/c{i}.xhtml", f"<html><body>{body}</body></html>")
            items.append(f'<item id="c{i}" href="c{i}.xhtml" media-type="application/xhtml+xml"/>')
            refs.append(f'<itemref idref="c{i}"/>')
            nav.append(f'<li><a href="c{i}.xhtml">{title}</a>'
                       + (f"<ol>{''.join(sub)}</ol>" if sub else "") + "</li>")
        z.writestr("OEBPS/nav.xhtml", f'<html><body><nav epub:type="toc"><ol>{"".join(nav)}'
                                      f"</ol></nav></body></html>")
        z.writestr("OEBPS/c.opf",
                   '<package><metadata><dc:title>T</dc:title></metadata><manifest>'
                   '<item id="nav" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/>'
                   + "".join(items) + "</manifest><spine>" + "".join(refs) + "</spine></package>")


def test_epub_counts_split_at_headings(tmp_path):
    f = tmp_path / "b.epub"
    _epub(f, [("One", [(None, None, 100), ("s1", "One A", 250), ("s2", "One B", 400)]),
              ("Two", [(None, None, 600)])])
    rm = generate_roadmap(str(f), "epub")
    counts = pw.compute_counts(str(f), "epub", rm)
    by_title = dict(zip([n.title for n in rm.nodes], counts.own))
    # heading words count towards the entry they open
    assert by_title == {"One": 101, "One A": 252, "One B": 402, "Two": 601}
    assert counts.total == sum(counts.own) and not counts.estimated
    assert counts.subtree(rm, 0) == 755
    assert pw.words_before(rm, counts, 1, 0.0) == 755


def test_markdown_counts(tmp_path):
    f = tmp_path / "b.md"
    f.write_text(f"# Alpha\n\n{words(300)}\n\n## Alpha two\n\n{words(200)}\n\n"
                 f"# Beta\n\n{words(500)}\n", encoding="utf-8")
    rm = generate_roadmap(str(f), "md", "b")
    counts = pw.compute_counts(str(f), "md", rm, "b")
    assert dict(zip([n.title for n in rm.nodes], counts.own)) == {
        "Alpha": 301, "Alpha two": 202, "Beta": 501}


fitz = pytest.importorskip("pymupdf")


def test_pdf_counts_by_page_range(tmp_path):
    f = tmp_path / "b.pdf"
    doc = fitz.open()
    for i in range(6):
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 800), words(100 + i * 10, "word"), fontsize=9)
    doc.set_toc([[1, "Part A", 1], [1, "Part B", 3], [2, "B.1", 5]])
    doc.save(f)
    rm = generate_roadmap(str(f), "pdf")
    counts = pw.compute_counts(str(f), "pdf", rm)
    assert counts.own == [100 + 110, 120 + 130, 140 + 150]
    assert counts.subtree(rm, 1) == 540 and not counts.estimated


def test_scanned_pdf_is_an_estimate(tmp_path):
    f = tmp_path / "scan.pdf"
    doc = fitz.open()
    for _ in range(12):
        doc.new_page().draw_rect(fitz.Rect(50, 50, 500, 700), fill=(0.8, 0.8, 0.8))
    doc.save(f)
    rm = generate_roadmap(str(f), "pdf")
    assert rm.source == "pages"
    counts = pw.compute_counts(str(f), "pdf", rm)
    assert counts.estimated and counts.total == 12 * pw.AVG_WORDS_PER_PAGE


def test_word_cache_round_trip(tmp_path):
    f = tmp_path / "b.md"
    f.write_text("# A\n\nsome words here\n\n# B\n\nmore words\n", encoding="utf-8")
    rm = generate_roadmap(str(f), "md", "b")
    counts = pw.compute_counts(str(f), "md", rm, "b")
    pw.save_cached(99, str(f), counts)
    assert pw.load_cached(99, str(f), rm) == counts
    rm.nodes[0].title = "changed"                     # a different roadmap: cache is stale
    assert pw.load_cached(99, str(f), rm) is None


# -- opening later parts, and today's reading across books --------------------------------- #

def test_later_parts_open_where_they_begin(tmp_path):
    f = tmp_path / "b.md"
    f.write_text(f"# Alpha\n\n{words(2300)}\n\n# Beta\n\n{words(4600)}\n", encoding="utf-8")
    rm = generate_roadmap(str(f), "md", "b")
    counts = pw.compute_counts(str(f), "md", rm, "b")
    s = settings(study_factor=1.0, minutes_per_day=10)       # Beta: 20 min = 2 days
    tasks = rp.build_tasks(rm, counts, s)
    sched = rp.schedule(tasks, s)
    beta = [b for b in sched.blocks if b.key == tasks[1].key]
    assert [(b.part, b.before) for b in beta] == [(1, 0), (2, 10)]
    assert rp.block_location(counts, tasks[1], beta[0]) == (1, 0.0)
    index, ratio = rp.block_location(counts, tasks[1], beta[1])
    assert index == 1 and 0.45 < ratio < 0.55                  # halfway through Beta
    assert counts.location(10 ** 9) == (1, 0.999)


def test_pdf_location_is_a_page():
    counts = pw.WordCounts([300, 300], 600, 0, False, "", units=[100, 200, 300], starts=[0, 300])
    assert counts.location(150) == (1, 0.25)
    assert counts.location(0) == (0, 0.0)


class FakeLibrary:
    """Just enough of Library for plan_agenda (plans in memory)."""
    def __init__(self, books, plans):
        self.books, self.plans = books, plans

    def planned_books(self):
        return list(self.plans)

    def get(self, book_id):
        return self.books.get(book_id)

    def get_plan(self, book_id):
        return self.plans.get(book_id)


def test_todays_reading_across_books(tmp_path):
    from book_reader.services import plan_agenda
    from book_reader.services import roadmap as rmod
    books, plans = {}, {}
    for bid, n in ((1, 3), (2, 2)):
        f = tmp_path / f"b{bid}.md"
        f.write_text("".join(f"# Ch {i}\n\n{words(4600)}\n\n" for i in range(n)), encoding="utf-8")
        road = generate_roadmap(str(f), "md", f.stem)
        rmod.save_cached(bid, str(f), road)
        pw.save_cached(bid, str(f), pw.compute_counts(str(f), "md", road, f.stem))
        books[bid] = dict(path=str(f), title=f"Book {bid}", last_read_at=bid)
        plans[bid] = rp.ReadingPlan.new(MON, minutes_per_day=30, study_factor=1.5).to_json()
    # book 3 has a plan but no caches yet
    books[3] = dict(path=str(tmp_path / "b1.md"), title="Book 3", last_read_at=0)
    plans[3] = plans[1]
    lib = FakeLibrary(books, plans)

    tue = MON + timedelta(days=1)
    agenda = plan_agenda.todays_reading(lib, today=tue)
    real = [i for i in agenda.items if not i.stale]
    assert agenda.planned == 3 and agenda.books == 2
    assert [i.overdue for i in real] == [True, True, False, False]   # catch up first
    assert agenda.behind_minutes == 60 and agenda.minutes == 120
    assert real[0].book == "Book 2"                                  # read most recently
    assert agenda.items[-1].stale and agenda.items[-1].book == "Book 3"

    # ticking off Book 2's Monday chapter removes it from the agenda
    plan = rp.ReadingPlan.from_json(plans[2])
    road = rmod.load_cached(2, books[2]["path"])
    tasks = rp.build_tasks(road, pw.load_cached(2, books[2]["path"], road), plan.settings)
    rp.set_done(plan, tasks[0].key, True, MON)
    plans[2] = plan.to_json()
    agenda = plan_agenda.todays_reading(lib, today=tue)
    assert agenda.behind_minutes == 30


def test_book_overview_for_the_reminder(tmp_path):
    from book_reader.services import plan_agenda
    from book_reader.services import roadmap as rmod
    f = tmp_path / "b.md"
    f.write_text("".join(f"# Ch {i}\n\n{words(4600)}\n\n" for i in range(7)), encoding="utf-8")
    road = generate_roadmap(str(f), "md", "b")
    rmod.save_cached(1, str(f), road)
    pw.save_cached(1, str(f), pw.compute_counts(str(f), "md", road, "b"))
    plan = rp.ReadingPlan.new(MON, minutes_per_day=30, study_factor=1.5)
    lib = FakeLibrary({1: dict(path=str(f), title="B", last_read_at=1)}, {1: plan.to_json()})
    wed = MON + timedelta(days=2)
    ov = plan_agenda.overview(lib, 1, today=wed)
    assert ov.status == "1 h behind" and ov.behind and ov.percent == 0
    assert [i.overdue for i in ov.today] == [True, True, False]
    assert [w.planned for w in ov.week] == [30, 30, 30, 0, 0, 30, 30]   # Wed .. Tue
    assert [w.reading_day for w in ov.week] == [True, True, True, False, False, True, True]
    sat = MON + timedelta(days=5)
    ov = plan_agenda.overview(lib, 1, today=sat)                     # weekend: what's next
    assert [i for i in ov.today if not i.overdue] == []
    assert ov.next_day == MON + timedelta(days=7) and len(ov.next_items) == 1
    assert plan_agenda.overview(lib, 2) is None
