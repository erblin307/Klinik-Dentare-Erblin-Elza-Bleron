"use client";

import { useEffect, useMemo, useState } from "react";

import { useChat } from "@/components/chat/ChatProvider";
import { Icon } from "@/components/ui/Icon";
import type { Dictionary } from "@/dictionaries";
import { clinicDate, formatDate, formatTime, interpolate } from "@/lib/format";
import type { Locale } from "@/lib/locale";
import type { Dentist, Service, Slot } from "@/lib/types";

const DAYS_SHOWN = 14;

type Props = {
  clinicSlug: string;
  timezone: string;
  phone: string;
  locale: Locale;
  services: Service[];
  dentists: Dentist[];
  initialServiceId: number | null;
  initialDentistId: number | null;
  t: Dictionary["book"];
  handoffTemplate: string;
};

type Result = { key: string; slots: Slot[]; error: "error" | "rateLimited" | null };

export function BookingPlanner(props: Props) {
  const { clinicSlug, timezone, phone, locale, t } = props;
  const chat = useChat();
  const bookable = props.services.filter((s) => s.dentist_ids.length > 0);

  const [serviceId, setServiceId] = useState<number | null>(() => {
    const fromDentist = props.initialDentistId
      ? bookable.find((s) => s.dentist_ids.includes(props.initialDentistId!))?.id
      : undefined;
    return bookable.find((s) => s.id === props.initialServiceId)?.id ?? fromDentist ?? null;
  });
  const [dentistId, setDentistId] = useState<number | null>(props.initialDentistId);
  const [day, setDay] = useState(() => clinicDate(timezone));
  const [result, setResult] = useState<Result | null>(null);
  const [selected, setSelected] = useState<{ key: string; slot: Slot } | null>(null);

  const service = bookable.find((s) => s.id === serviceId) ?? null;
  const performers = props.dentists.filter((d) => service?.dentist_ids.includes(d.id));
  const effectiveDentist = performers.some((d) => d.id === dentistId) ? dentistId : null;
  const key = service ? `${service.id}|${effectiveDentist ?? ""}|${day}` : "";
  const days = useMemo(() => Array.from({ length: DAYS_SHOWN }, (_, i) => clinicDate(timezone, i)), [timezone]);

  useEffect(() => {
    if (!key) return;
    const controller = new AbortController();
    const [service, dentist, date] = key.split("|");
    const query = new URLSearchParams({ service, date, ...(dentist && { dentist }) });
    fetch(`/api/public/clinics/${encodeURIComponent(clinicSlug)}/availability?${query}`, { signal: controller.signal })
      .then(async (response) => {
        if (response.status === 429) return setResult({ key, slots: [], error: "rateLimited" });
        if (!response.ok) return setResult({ key, slots: [], error: "error" });
        const data = (await response.json()) as { slots: Slot[] };
        setResult({ key, slots: data.slots, error: null });
      })
      .catch((error: unknown) => {
        if ((error as Error).name !== "AbortError") setResult({ key, slots: [], error: "error" });
      });
    return () => controller.abort();
  }, [key, clinicSlug]);

  const loading = Boolean(key) && result?.key !== key;
  const slots = !loading && result ? result.slots : [];
  const chosen = selected?.key === key ? selected.slot : null;

  if (!bookable.length) {
    return <p className="text-muted">{t.noServices}</p>;
  }

  const continueInChat = () => {
    if (!service || !chosen) return;
    void chat.handoff(
      interpolate(props.handoffTemplate, {
        service: service.name,
        date: clinicDate(timezone, 0, new Date(chosen.start)),
        time: formatTime(chosen.start, locale, timezone),
        dentist: chosen.dentist,
      }),
    );
  };

  return (
    <div className="grid gap-12 lg:grid-cols-12">
      <div className="space-y-10 lg:col-span-7">
        <fieldset>
          <legend className="mb-4 text-xs font-medium tracking-[0.18em] text-brass uppercase">
            <span className="mr-3 tabular-nums">01</span>
            {t.service}
          </legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {bookable.map((s) => (
              <label
                key={s.id}
                className={`flex cursor-pointer items-baseline justify-between gap-4 rounded-xl border px-4 py-3.5 transition has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-forest ${
                  s.id === serviceId ? "border-forest bg-paper" : "border-line bg-paper/60 hover:border-forest/50"
                }`}
              >
                <input
                  type="radio"
                  name="service"
                  value={s.id}
                  checked={s.id === serviceId}
                  onChange={() => setServiceId(s.id)}
                  className="sr-only"
                />
                <span className="font-display text-xl leading-tight">{s.name}</span>
                <span className="shrink-0 text-xs text-muted tabular-nums">{s.duration_minutes} min</span>
              </label>
            ))}
          </div>
        </fieldset>

        {service && performers.length > 1 && (
          <div>
            <label htmlFor="dentist" className="mb-3 block text-xs font-medium tracking-[0.18em] text-brass uppercase">
              {t.dentist}
            </label>
            <select
              id="dentist"
              value={effectiveDentist ?? ""}
              onChange={(event) => setDentistId(event.target.value ? Number(event.target.value) : null)}
              className="h-12 w-full rounded-xl border border-line bg-paper px-4 sm:w-80"
            >
              <option value="">{t.anyDentist}</option>
              {performers.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {service && (
          <fieldset>
            <legend className="mb-4 text-xs font-medium tracking-[0.18em] text-brass uppercase">
              <span className="mr-3 tabular-nums">02</span>
              {t.day}
            </legend>
            <div className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-2">
              {days.map((d) => (
                <button
                  key={d}
                  type="button"
                  aria-pressed={d === day}
                  onClick={() => setDay(d)}
                  className={`flex min-w-[4.5rem] snap-start flex-col items-center rounded-xl border px-3 py-2.5 text-sm transition ${
                    d === day ? "border-forest bg-forest text-ivory" : "border-line bg-paper hover:border-forest/50"
                  }`}
                >
                  <span className="text-[11px] tracking-wider uppercase opacity-80">
                    {formatDate(d, locale, timezone, "short").split(/[,\s]/)[0]}
                  </span>
                  <span className="font-display text-2xl leading-tight lining-nums tabular-nums">{Number(d.slice(8))}</span>
                </button>
              ))}
            </div>
            <label className="mt-4 inline-flex items-center gap-3 text-sm text-muted">
              {t.otherDay}
              <input
                type="date"
                value={day}
                min={days[0]}
                onChange={(event) => event.target.value && setDay(event.target.value)}
                className="h-10 rounded-lg border border-line bg-paper px-3 text-ink"
              />
            </label>
          </fieldset>
        )}
      </div>

      <div className="lg:col-span-5">
        <div className="rounded-2xl border border-line bg-paper p-6 lg:sticky lg:top-28">
          <h2 className="font-sans text-xs font-medium tracking-[0.18em] text-brass uppercase">
            <span className="mr-3 tabular-nums">03</span>
            {t.times}
          </h2>
          {!service ? (
            <p className="mt-4 text-sm text-muted">{t.chooseService}</p>
          ) : (
            <>
              <p className="mt-2 font-display text-2xl first-letter:uppercase">{formatDate(day, locale, timezone)}</p>
              <div aria-live="polite" className="mt-5">
                {loading && <p className="text-sm text-muted">{t.loading}</p>}
                {!loading && result?.error && <p className="text-sm">{result.error === "rateLimited" ? t.rateLimited : t.error}</p>}
                {!loading && !result?.error && slots.length === 0 && <p className="text-sm text-muted">{t.noSlots}</p>}
                {!loading && slots.length > 0 && (
                  <ul className="grid grid-cols-3 gap-2">
                    {slots.map((slot) => {
                      const isChosen = chosen?.start === slot.start && chosen.dentist_id === slot.dentist_id;
                      return (
                        <li key={`${slot.start}-${slot.dentist_id}`}>
                          <button
                            type="button"
                            aria-pressed={isChosen}
                            onClick={() => setSelected({ key, slot })}
                            title={slot.dentist}
                            className={`w-full rounded-lg border px-2 py-2 text-sm tabular-nums transition ${
                              isChosen ? "border-forest bg-forest text-ivory" : "border-line hover:border-forest"
                            }`}
                          >
                            {formatTime(slot.start, locale, timezone)}
                            {performers.length > 1 && !effectiveDentist && (
                              <span className="block truncate text-[10px] opacity-75">{slot.dentist}</span>
                            )}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
              {chosen && (
                <div className="mt-6 border-t border-line pt-5">
                  <p className="text-sm font-medium">
                    {interpolate(t.selection, {
                      service: service.name,
                      date: formatDate(chosen.start, locale, timezone, "short"),
                      time: formatTime(chosen.start, locale, timezone),
                      dentist: chosen.dentist,
                    })}
                  </p>
                  <button
                    type="button"
                    onClick={continueInChat}
                    disabled={!chat.clinic.slug}
                    className="mt-4 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-full bg-forest px-6 text-sm font-medium text-ivory hover:bg-forest-deep"
                  >
                    <Icon name="chat" className="h-4 w-4" />
                    {t.continue}
                  </button>
                  <p className="mt-3 text-xs leading-relaxed text-muted">{t.note}</p>
                </div>
              )}
            </>
          )}
          {phone && (
            <p className="mt-6 border-t border-line pt-4 text-sm text-muted">
              {interpolate(t.callInstead, { phone: "" })}
              <a href={`tel:${phone.replace(/\s/g, "")}`} className="font-medium text-forest underline underline-offset-4">
                {phone}
              </a>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
