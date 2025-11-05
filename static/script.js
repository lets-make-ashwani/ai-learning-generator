// UI logic for generate, flashcards flip, MCQ submit/score, downloads
document.addEventListener("DOMContentLoaded", () => {
  const modeTabs = document.querySelectorAll(".mode-tab");
  const topicInput = document.getElementById("topic-input");
  const numInput = document.getElementById("num-cards-input");
  const generateBtn = document.getElementById("generate-button");
  const flashcardContainer = document.getElementById("flashcard-container");
  const quizContainer = document.getElementById("quiz-container");
  const messageArea = document.getElementById("message-area");
  const difficultySelect = document.getElementById("difficulty");
  let currentMode = "flashcard";

  // --- Mode switch (Flashcards / MCQ) ---
  modeTabs.forEach(btn => btn.addEventListener("click", () => {
    modeTabs.forEach(t => t.classList.remove("bg-indigo-600", "text-white"));
    btn.classList.add("bg-indigo-600", "text-white");
    currentMode = btn.dataset.mode || (btn.textContent.trim().toLowerCase() === "mcq" ? "mcq" : "flashcard");
    flashcardContainer.classList.toggle("hidden", currentMode !== "flashcard");
    quizContainer.classList.toggle("hidden", currentMode !== "mcq");
    updateGenerateText();
  }));

  function updateGenerateText() {
    const n = parseInt(numInput.value) || 5;
    generateBtn.textContent =
      currentMode === "flashcard"
        ? `Generate Flashcards (${n})`
        : `Generate MCQ Quiz (${n})`;
  }
  numInput.addEventListener("input", updateGenerateText);
  updateGenerateText();

  function showMessage(text, type = "info") {
    messageArea.innerHTML = `<div class="p-3 rounded ${type === "error" ? "bg-rose-600" : "bg-slate-700"}">${text}</div>`;
  }

  // --- Generate content ---
  generateBtn.addEventListener("click", async () => {
    const topic = topicInput.value.trim();
    const num = parseInt(numInput.value);
    const difficulty = difficultySelect.value;
    if (!topic) {
      showMessage("Enter a topic.", "error");
      return;
    }
    if (isNaN(num) || num < 1) {
      showMessage("Enter a valid count.", "error");
      return;
    }
    showMessage("Generating... please wait (may take a few seconds)");
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          numItems: num,
          mode: currentMode,
          difficulty,
          explanations: true,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        showMessage(data.error || "Generation failed.", "error");
        return;
      }
      const items = data.items || [];
      if (currentMode === "flashcard") renderFlashcards(items, data.generation_id);
      else renderQuiz(items, data.generation_id);
    } catch (e) {
      console.error(e);
      showMessage("Generation failed. Try again.", "error");
    }
  });

  // --- FLASHCARDS ---
  function renderFlashcards(cards) {
    flashcardContainer.innerHTML = "";
    showMessage(`Generated ${cards.length} flashcards. Click a card to flip.`);

    cards.forEach((c, idx) => {
      const q = c.question || c.front || `Question ${idx + 1}`;
      const a = c.answer || c.back || "";

      const outer = document.createElement("div");
      outer.className = "relative w-full mb-4 transition-all duration-500";

      const card = document.createElement("div");
      card.className =
        "flashcard rounded-xl shadow-lg transform-gpu transition-transform duration-700 ease-in-out";
      card.innerHTML = `
        <div class="card-face card-front p-5 font-semibold flex justify-center items-center">
          ${escapeHtml(q)}
        </div>
        <div class="card-face card-back p-5 flex justify-center items-center">
          ${escapeHtml(a)}
        </div>
      `;

      card.addEventListener("click", () => {
        card.classList.toggle("flipped");
        setTimeout(() => {
          const activeFace = card.classList.contains("flipped")
            ? card.querySelector(".card-back")
            : card.querySelector(".card-front");
          outer.style.height = activeFace.scrollHeight + "px";
        }, 400);
      });

      setTimeout(() => {
        outer.style.height = card.querySelector(".card-front").scrollHeight + "px";
      }, 0);

      outer.appendChild(card);
      flashcardContainer.appendChild(outer);
    });
  }

  // --- MCQ ---
  function renderQuiz(questions) {
    quizContainer.innerHTML = "";
    showMessage(`Generated ${questions.length} MCQs. Select answers and click Submit.`);

    questions.forEach((q, i) => {
      const container = document.createElement("div");
      container.className = "p-4 bg-slate-700 rounded";

      const title = document.createElement("div");
      title.className = "font-semibold mb-2";
      title.textContent = `${i + 1}. ${q.question}`;
      container.appendChild(title);

      const opts = q.options || [];
      opts.forEach((opt) => {
        const label = document.createElement("label");
        label.className = "block p-2 mb-1 bg-slate-800 rounded cursor-pointer flex items-center gap-2";

        label.innerHTML = `
          <span class="checkmark hidden text-emerald-400 font-bold transition-transform duration-200">✓</span>
          <input type="radio" name="q${i}" value="${escapeHtml(opt)}" class="hidden">
          <span>${escapeHtml(opt)}</span>
        `;

        label.addEventListener("click", () => {
          document.querySelectorAll(`input[name="q${i}"]`).forEach(inp => {
            inp.closest("label").querySelector(".checkmark").classList.add("hidden");
          });
          label.querySelector(".checkmark").classList.remove("hidden");
        });

        container.appendChild(label);
      });

      quizContainer.appendChild(container);
    });

    const submitWrap = document.createElement("div");
    submitWrap.className = "text-center mt-6";
    submitWrap.innerHTML = `<button id="submit-quiz" class="px-6 py-3 bg-emerald-600 rounded font-semibold">Submit Quiz</button>`;
    quizContainer.appendChild(submitWrap);

    document.getElementById("submit-quiz").addEventListener("click", () => {
      gradeQuiz(questions);
    });
  }

  // --- Grade quiz ---
  function gradeQuiz(questions) {
    let correct = 0;
    const total = questions.length;

    questions.forEach((q, i) => {
      const selected = document.querySelector(`input[name="q${i}"]:checked`);
      const chosen = selected ? selected.value : null;
      const correctAns = q.correct_answer || q.answer || null;

      const labels = document.querySelectorAll(`input[name="q${i}"]`);
      labels.forEach((inp) => {
        const lab = inp.closest("label");
        lab.classList.remove("bg-green-700", "bg-rose-700");
        if (inp.value === correctAns) lab.classList.add("bg-green-700");
        if (chosen && inp.value === chosen && chosen !== correctAns)
          lab.classList.add("bg-rose-700");
      });

      if (chosen && correctAns && chosen === correctAns) correct++;
    });

    const pct = Math.round((correct / total) * 100);
    showMessage(`You scored ${correct}/${total} (${pct}%).`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // --- Helper ---
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
});
