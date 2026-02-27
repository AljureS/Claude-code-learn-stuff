import { renderToPipeableStream } from "react-dom/server";
import ClassPage from "./page";
import { Class } from "@/types";
import { describe, it, expect, vi } from "vitest";
import { Writable } from "stream";

vi.mock("@/components/VideoPlayer/VideoPlayer", () => ({
  VideoPlayer: ({ src, title }: { src: string; title: string }) => (
    <div data-testid="mock-video-player">
      {title} - {src}
    </div>
  ),
}));

// Mock de fetch que resuelve inmediatamente
global.fetch = vi.fn().mockResolvedValue({
  ok: true,
  json: () =>
    Promise.resolve({
      id: 19,
      name: "Clase de Test",
      description: "Descripción de la clase de test",
      slug: "clase-test",
    } as Class),
});

function renderToStringAsync(element: React.ReactElement): Promise<string> {
  return new Promise((resolve, reject) => {
    let html = "";
    const writable = new Writable({
      write(chunk, _encoding, callback) {
        html += chunk.toString();
        callback();
      },
    });
    const { pipe } = renderToPipeableStream(element, {
      onAllReady() {
        pipe(writable);
        writable.on("finish", () => resolve(html));
      },
      onError: reject,
    });
  });
}

describe("ClassPage", () => {
  it("renders class info and video", async () => {
    const params = Promise.resolve({ class_id: "19" });
    const html = await renderToStringAsync(<ClassPage params={params} />);

    expect(html).toContain("Clase de Test");
    expect(html).toContain("Descripción de la clase de test");
    expect(html).toContain("mock-video-player");
    expect(html).toContain("Regresar al curso");
  }, 10000);
});
