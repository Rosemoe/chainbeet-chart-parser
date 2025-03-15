from parser import NoteInfo, Note
import math
import skia as sk


def analyze_beat_lines(chart: NoteInfo) -> list[float]:
    bpm_changes = [x for x in chart.notes if x.note_type == 2]
    max_time = max(x.time for x in chart.notes)
    curr_bpm = chart.bpm
    curr_time = 0.0
    timings: list[float] = []
    curr_index = 0
    while True:
        limit_time = max_time if curr_index >= len(bpm_changes) else bpm_changes[curr_index].time
        delta_time = 60 / curr_bpm * 4
        while curr_time + delta_time < limit_time:
            curr_time += delta_time
            timings.append(curr_time)
        if curr_index < len(bpm_changes):
            curr_bpm = bpm_changes[curr_index].bpm
            timings.append(bpm_changes[curr_index].time)
        else:
            break
        curr_index += 1
    return timings


def analyze_coincident_lines(notes: list[Note]) -> list[tuple[float, list[Note]]]:
    timings: dict[float, list[Note]] = {}
    for note in notes:
        if note.is_meta_note():
            continue
        if note.time not in timings:
            timings[note.time] = []
        timings[note.time].append(note)
    result: list[tuple[float, list[Note]]] = []
    for time, note_list in timings.items():
        if len(note_list) < 2:
            continue
        note_list.sort(key=lambda x: x.position)
        result.append((time, note_list))
    return result


def analyze_beats(notes: list) -> list[tuple[float, int]]:
    timings: list[float] = []
    timing_bpm: dict[float, float] = {}
    for note in notes:
        if note.is_meta_note():
            continue
        timings.append(note.time)
        timing_bpm[note.time] = note.bpm
    timings = sorted(list(set(timings)))
    result: list[tuple[float, int]] = []
    error_tolerance: float = 0.05
    for i in range(len(timings)):
        curr = timings[i]
        time_delta = 60.0 / timing_bpm[curr] * 4
        beat = 0
        # if i > 0:
        #     prev = time_delta / (curr - timings[i - 1])
        #     if abs(prev - round(prev)) < error_tolerance:
        #         beat = max(beat, round(prev))
        if i < len(timings) - 1:
            nxt = time_delta / (timings[i + 1] - curr)
            if abs(nxt - round(nxt)) < error_tolerance:
                beat = max(beat, round(nxt))
        if beat % 2 == 0 and beat:
            result.append((curr, beat))
    return result


def _create_charge_path(extra_width: float = 0.0):
    half_width = extra_width / 2
    path = sk.Path()
    a = 5 * (3 ** 0.5)
    path.moveTo(-10 - half_width, 0)
    path.lineTo(-5 - half_width, -a)
    path.lineTo(5 + half_width, -a)
    path.lineTo(10 + half_width, 0)
    path.lineTo(5 + half_width, a)
    path.lineTo(-5 - half_width, a)
    path.close()
    return path


def _create_chain_path():
    path = sk.Path()
    path.moveTo(0, -10)
    path.lineTo(10, 0)
    path.lineTo(0, 10)
    path.lineTo(-10, 0)
    path.close()
    return path


class ChainbeetRenderConfig:
    height_factor: int = 300
    track_width: int = 450
    height_extra: int = 100
    width_extra: int = 150
    width_scale: float = 0.9
    page_height: int = 3000

    min_time_scale: float = 0.5
    max_time_scale: float = 2.0


class ChainbeetRenderer:
    def __init__(self, chart: NoteInfo, config: ChainbeetRenderConfig):
        self.config = config
        self.chart = chart
        self.bpm = chart.bpm
        self.notes: list[Note] = chart.notes.copy()
        self.notes.sort(key=lambda x: x.time)
        self.speed_changes = [x for x in self.notes if x.note_type == 3]

    def compute_time_y(self, time: float) -> float:
        current_sum = 0.0
        last_change_time = 0.0
        current_speed = 1.0
        for i in range(len(self.speed_changes)):
            if time > self.speed_changes[i].time:
                current_sum += current_speed * (self.speed_changes[i].time - last_change_time)
                last_change_time = self.speed_changes[i].time
                current_speed = min(max(self.config.min_time_scale, self.speed_changes[i].time_scale), self.config.max_time_scale)
            else:
                break
        if time > last_change_time:
            current_sum += current_speed * (time - last_change_time)
        return current_sum * self.config.height_factor

    def render(self) -> sk.Image:
        notes = self.notes
        max_time = max(x.time for x in notes)
        height = int(self.compute_time_y(max_time)) + 1
        width = self.config.track_width
        surface = sk.Surface(width + self.config.width_extra, height + self.config.height_extra)
        canvas: sk.Canvas = surface.getCanvas()
        canvas.translate(self.config.width_extra / 2, self.config.height_extra / 2)
        tap_paint = sk.Paint(Color=0xff7b013d, AntiAlias=True)
        note_stroke_paint = sk.Paint(Color=0xffe8c9c7, AntiAlias=True, Style=sk.Paint.kStroke_Style, StrokeWidth=2.5)
        note_bold_stroke_paint = sk.Paint(Color=0xffe8c9c7, AntiAlias=True, Style=sk.Paint.kStroke_Style, StrokeWidth=4)
        chain_paint = sk.Paint(Color=0xff004a80)
        charge_paint = sk.Paint(Color=0xff3c7b1e)
        charge_segment_paint = sk.Paint(Color=0xff374219, AntiAlias=True)
        charge_segment_stroke_paint = sk.Paint(Color=0xdde8c9c7, AntiAlias=True, Style=sk.Paint.kStroke_Style,
                                               StrokeWidth=1)
        chain_connection_paint = sk.Paint(Color=0xffeeeeee, AntiAlias=True,
                                          PathEffect=sk.DashPathEffect.Make([15, 15], 0))
        line_paint = sk.Paint(Color=0xffeeeeee)
        beat_line_paint = sk.Paint(Color=0xff888888, StrokeWidth=1)
        chain_path = _create_chain_path()
        for note in notes:
            note.position -= (note.position - 0.5) * (1.0 - self.config.width_scale)
        layer_paint = sk.Paint(Color=0x11ffff00)
        # Speed Change Hint
        for i in range(len(self.speed_changes)):
            if self.speed_changes[i].time_scale != 1:
                limit_time = max_time if i + 1 >= len(self.speed_changes) else self.speed_changes[i + 1].time
                canvas.drawRect(sk.Rect(0, height - self.compute_time_y(limit_time), width, height - self.compute_time_y(self.speed_changes[i].time)), layer_paint)
        # Beatline Hint
        for time in analyze_beat_lines(self.chart):
            y = height - self.compute_time_y(time)
            canvas.drawLine(0, y, width, y, beat_line_paint)
        analyzed_lines = analyze_coincident_lines(notes)
        for time, note_list in analyzed_lines:
            y = height - self.compute_time_y(time)
            start_pos = min(x.position for x in note_list)
            end_pos = max(x.position for x in note_list)
            canvas.drawLine(start_pos * width, y, end_pos * width, y, line_paint)
        # Chart Notes
        coincident_timings = set(x[0] for x in analyzed_lines)
        notes.sort(key=lambda x: x.time)
        for note in notes:
            if note.is_tap_note():
                note_width = width * note.width * self.config.width_scale if note.is_wide_note() else 20
                y = height - self.compute_time_y(note.time)
                rect = sk.Rect(width * note.position - note_width / 2, y - 10,
                               width * note.position + note_width / 2, y + 10)
                canvas.drawRoundRect(rect, 10, 10, tap_paint)
                canvas.drawRoundRect(rect, 10, 10,
                                     note_bold_stroke_paint if note.time in coincident_timings else note_stroke_paint)
            elif note.is_chain_note(0):
                if note.next_note:
                    start_x, start_y = width * note.position, height - self.compute_time_y(note.time)
                    end_x, end_y = width * note.next_note.position, height - self.compute_time_y(note.next_note.time)
                    canvas.drawLine(start_x, start_y, end_x, end_y, chain_connection_paint)
                chain_path.offset(width * note.position, height - self.compute_time_y(note.time))
                canvas.drawPath(chain_path, chain_paint)
                canvas.drawPath(chain_path,
                                note_bold_stroke_paint if note.time in coincident_timings else note_stroke_paint)
                chain_path.offset(-width * note.position, -(height - self.compute_time_y(note.time)))
            elif note.is_long_note():
                note_width = width * note.width * self.config.width_scale if note.is_wide_note() else 20
                if note.next_note:
                    start_x, start_y = width * note.position, height - self.compute_time_y(note.time)
                    end_x, end_y = width * note.next_note.position, height - self.compute_time_y(note.next_note.time)
                    path = sk.Path()
                    path.moveTo(start_x - note_width / 2, start_y)
                    path.lineTo(start_x + note_width / 2, start_y)
                    path.lineTo(end_x + note_width / 2, end_y)
                    path.lineTo(end_x - note_width / 2, end_y)
                    path.close()
                    canvas.drawPath(path, charge_segment_paint)
                    canvas.drawPath(path, charge_segment_stroke_paint)
                charge_path = _create_charge_path(note_width - 20)
                charge_path.offset(width * note.position, height - self.compute_time_y(note.time))
                canvas.drawPath(charge_path, charge_paint)
                canvas.drawPath(charge_path,
                                note_bold_stroke_paint if note.time in coincident_timings else note_stroke_paint)
                charge_path.offset(-width * note.position, -(height - self.compute_time_y(note.time)))
        # Note Beat Text Hint
        text_paint = sk.Paint(Color=0xffffffff)
        text_font = sk.Font()
        text_font.setSize(20)
        for time, split in analyze_beats(notes):
            y = height - self.compute_time_y(time)
            x = width + 10
            canvas.drawString(str(split), x, y + text_font.getMetrics().fDescent, text_font, text_paint)
        # Speed Change Text Hint
        for i in range(len(self.speed_changes)):
            y = height - self.compute_time_y(self.speed_changes[i].time)
            text = '{:g}x'.format(self.speed_changes[i].time_scale)
            x = -10 - text_font.measureText(text)
            canvas.drawString(text, x, y + text_font.getMetrics().fDescent, text_font, text_paint)
        paint = sk.Paint(Color=0xffffffff)
        # Chart Boundary Lines
        canvas.drawLine(0, 0, 0, height, paint)
        canvas.drawLine(width, 0, width, height, paint)
        image: sk.Image = surface.makeImageSnapshot()
        # Split chart to pages
        height_limit = self.config.page_height
        required_page = math.ceil(surface.height() / height_limit)
        required_width = required_page * surface.width()
        surface_2 = sk.Surface(required_width, height_limit)
        canvas = surface_2.getCanvas()
        canvas.drawColor(0xff080403)
        for i in range(required_page):
            top_y, bottom_y = surface.height() - height_limit * (i + 1), surface.height() - height_limit * i
            src_rect = sk.Rect(0, top_y, surface.width(), bottom_y)
            dst_rect = sk.Rect(surface.width() * i, 0, surface.width() * (i + 1), height_limit)
            canvas.drawImageRect(image, src_rect, dst_rect)
        image = surface_2.makeImageSnapshot()
        return image
