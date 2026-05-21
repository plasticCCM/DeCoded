const modeButtons = document.querySelectorAll("#modeButtons .mode");
const modeSelect = document.getElementById("modeSelect");
const chatCard = document.querySelector(".chat-card");
const chatForm = document.getElementById("chatForm");
const chatMessages = document.getElementById("chatMessages");
const gameBtn = document.getElementById("gameBtn");
const gameArea = document.getElementById("gameArea");
const statusText = document.getElementById("statusText");
const resetChat = document.getElementById("resetChat");
const gameChoiceButtons = document.querySelectorAll(".game-choice");
const recentTopicList = document.getElementById("recentTopicList");
const understandingCard = document.getElementById("understandingCard");
const understandingRank = document.getElementById("understandingRank");
const understandingFill = document.getElementById("understandingFill");
const understandingCaption = document.getElementById("understandingCaption");
const topicPath = document.getElementById("topicPath");
const openProfile = document.getElementById("openProfile");
const closeProfile = document.getElementById("closeProfile");
const profileModal = document.getElementById("profileModal");
const profileOverallRank = document.getElementById("profileOverallRank");
const profileOverallScore = document.getElementById("profileOverallScore");
const profileTopicsCount = document.getElementById("profileTopicsCount");
const profileTopicList = document.getElementById("profileTopicList");
const profileCardList = document.getElementById("profileCardList");
const profileKnowledgeMap = document.getElementById("profileKnowledgeMap");

let hasAnswer = chatCard?.dataset.hasAnswer === "true";
let isAsking = false;
let isGameLoading = false;
let selectedGameType = "true_false";
let currentCompletedGames = new Set(
    (understandingCard?.dataset.completedGames || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
);
let currentProgress = {
    topic: understandingCard?.dataset.topic || "Тема не выбрана",
    score: Number(understandingCard?.dataset.score || 0),
    rank: understandingCard?.dataset.rank || "Coal",
};
let lastAnswerTopic = currentProgress.topic;
const rankClasses = ["rank-coal", "rank-bronze", "rank-silver", "rank-gold", "rank-ruby", "rank-diamond"];

function setStatus(message = "") {
    if (statusText) {
        statusText.textContent = message;
    }
}

function syncGameButton() {
    if (gameBtn) {
        gameBtn.disabled = !hasAnswer || isAsking || isGameLoading || currentCompletedGames.has(selectedGameType);
    }
}

function rankClassName(rank) {
    return `rank-${String(rank || "Coal").toLowerCase()}`;
}

function paintRank(element, rank) {
    if (!element) {
        return;
    }

    element.classList.remove(...rankClasses);
    element.classList.add(rankClassName(rank));
}

function syncGameChoices() {
    gameChoiceButtons.forEach((button) => {
        const gameType = button.dataset.gameType || "true_false";
        const completed = currentCompletedGames.has(gameType);
        button.classList.toggle("completed", completed);
        button.disabled = completed || isAsking || isGameLoading;
        button.title = completed ? "Эта мини-игра уже пройдена по текущей теме" : "";
    });

    if (currentCompletedGames.has(selectedGameType)) {
        const nextButton = Array.from(gameChoiceButtons).find((button) => !currentCompletedGames.has(button.dataset.gameType || ""));

        if (nextButton) {
            selectedGameType = nextButton.dataset.gameType || "true_false";
            gameChoiceButtons.forEach((choice) => choice.classList.remove("active"));
            nextButton.classList.add("active");
        }
    }

    syncGameButton();
}

function scrollChatToBottom() {
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function removeEmptyState() {
    document.getElementById("emptyState")?.remove();
}

function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function htmlToPlainText(html) {
    const template = document.createElement("template");
    template.innerHTML = html;
    return template.content.textContent || "";
}

async function typeAssistantMessage(messageNode, html) {
    const body = messageNode.querySelector(".message-body");

    if (!body) {
        return;
    }

    const plainText = htmlToPlainText(html).trim();

    if (!plainText) {
        body.innerHTML = html;
        return;
    }

    const totalCharacters = plainText.length;
    const targetDuration = Math.min(5200, Math.max(900, totalCharacters * 18));
    const frameDelay = 24;
    const chunkSize = Math.max(1, Math.ceil(totalCharacters / (targetDuration / frameDelay)));

    body.classList.add("typing");
    body.textContent = "";

    for (let index = 0; index < totalCharacters; index += chunkSize) {
        body.textContent = plainText.slice(0, index + chunkSize);
        scrollChatToBottom();
        await wait(frameDelay);
    }

    body.classList.remove("typing");
    body.innerHTML = html;
}

function createMessage(role, label, content, asHtml = false) {
    const article = document.createElement("article");
    article.className = `message message-${role}`;

    const labelNode = document.createElement("div");
    labelNode.className = "message-label";
    labelNode.textContent = label;

    const body = document.createElement("div");
    body.className = role === "assistant" ? "message-body rich-text" : "message-body";

    if (asHtml) {
        body.innerHTML = content;
    } else {
        body.textContent = content;
    }

    article.append(labelNode, body);
    return article;
}

function createAssistantSkeleton() {
    const message = createMessage("assistant", "Бот", "");
    const body = message.querySelector(".message-body");

    body.classList.remove("rich-text");
    body.classList.add("message-skeleton");
    body.setAttribute("aria-label", "Ответ загружается");

    const rows = [82, 94, 64];
    rows.forEach((width) => {
        const row = document.createElement("span");
        row.className = "skeleton-line";
        row.style.width = `${width}%`;
        body.appendChild(row);
    });

    return message;
}

function clearMessageSkeleton(messageNode) {
    const body = messageNode.querySelector(".message-body");

    if (!body) {
        return;
    }

    body.classList.remove("message-skeleton");
    body.classList.add("rich-text");
    body.removeAttribute("aria-label");
    body.replaceChildren();
}

function createUserMessage(content, mode = "") {
    const message = createMessage("user", "Вы", content);
    const body = message.querySelector(".message-body");

    if (mode && body) {
        const modeNode = document.createElement("div");
        modeNode.className = "message-mode";
        modeNode.textContent = `Режим: ${mode}`;
        message.insertBefore(modeNode, body);
    }

    return message;
}

function getTopicInput() {
    return chatForm?.querySelector("input[name='topic']");
}

function renderRecentTopics(topics = []) {
    if (!recentTopicList) {
        return;
    }

    recentTopicList.replaceChildren();

    if (!topics.length) {
        const empty = document.createElement("span");
        empty.className = "recent-topic-empty";
        empty.textContent = "Появятся после первого вопроса.";
        recentTopicList.appendChild(empty);
        return;
    }

    topics.slice(0, 5).forEach((topic) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "recent-topic";
        button.dataset.topic = topic;
        button.textContent = topic;
        recentTopicList.appendChild(button);
    });
}

function progressLabel(progress) {
    return `${progress.topic || "Тема не выбрана"}: ${progress.rank || "Coal"}, ${progress.score || 0}%`;
}

function renderTopicPath(steps = []) {
    if (!topicPath) {
        return;
    }

    topicPath.replaceChildren();

    steps.forEach((step, index) => {
        const item = document.createElement("div");
        item.className = `topic-path-step${step.done ? " done" : ""}`;
        item.dataset.stepKey = step.key || "";

        const number = document.createElement("span");
        number.setAttribute("aria-hidden", "true");
        number.textContent = String(index + 1);

        const label = document.createElement("strong");
        label.textContent = step.label || "";

        item.append(number, label);
        topicPath.appendChild(item);
    });
}

function updateProgressCard(progress) {
    if (!progress) {
        return;
    }

    currentProgress = {
        topic: progress.topic || currentProgress.topic || "Тема не выбрана",
        score: Number(progress.score || 0),
        rank: progress.rank || "Coal",
    };
    lastAnswerTopic = currentProgress.topic;
    currentCompletedGames = new Set(progress.completedGames || []);

    if (understandingCard) {
        understandingCard.dataset.topic = currentProgress.topic;
        understandingCard.dataset.score = String(currentProgress.score);
        understandingCard.dataset.rank = currentProgress.rank;
        understandingCard.dataset.completedGames = [...currentCompletedGames].join(",");
    }

    if (understandingRank) {
        understandingRank.textContent = currentProgress.rank;
        paintRank(understandingRank, currentProgress.rank);
    }

    if (understandingFill) {
        understandingFill.style.width = `${currentProgress.score}%`;
        understandingFill.parentElement?.setAttribute("aria-valuenow", String(currentProgress.score));
    }

    if (understandingCaption) {
        understandingCaption.textContent = progress.label || progressLabel(currentProgress);
    }

    renderTopicPath(progress.learningPath || []);
    syncGameChoices();
}

async function reportGameResult(correct, gameType = selectedGameType, completeGame = true) {
    try {
        const response = await fetch("/progress", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ correct, gameType, completeGame, topic: lastAnswerTopic }),
        });

        const data = await response.json().catch(() => ({}));

        if (response.ok && data.progress) {
            updateProgressCard(data.progress);
        }
    } catch (error) {
        setStatus("Прогресс обновится после следующей попытки");
        setTimeout(() => setStatus(""), 1800);
    }
}

function createProfileEmpty(text) {
    const empty = document.createElement("div");
    empty.className = "profile-empty";
    empty.textContent = text;
    return empty;
}

function renderProfile(data) {
    if (!data) {
        return;
    }

    if (profileOverallRank) {
        profileOverallRank.textContent = data.overall?.rank || "Coal";
        paintRank(profileOverallRank, data.overall?.rank || "Coal");
    }

    if (profileOverallScore) {
        profileOverallScore.textContent = `${data.overall?.score || 0}%`;
    }

    if (profileTopicsCount) {
        profileTopicsCount.textContent = String(data.overall?.topicsCount || 0);
    }

    if (profileKnowledgeMap) {
        profileKnowledgeMap.replaceChildren();
        const topics = data.topics || [];

        if (!topics.length) {
            profileKnowledgeMap.appendChild(createProfileEmpty("Карта появится после первого вопроса."));
        } else {
            topics.forEach((topic) => {
                const node = document.createElement("article");
                const score = Number(topic.score || 0);
                node.className = `knowledge-node ${rankClassName(topic.rank)}`;
                node.style.setProperty("--score", String(score));

                const rank = document.createElement("span");
                rank.textContent = topic.rank || "Coal";
                const title = document.createElement("strong");
                title.textContent = topic.title || "Тема";
                const percent = document.createElement("small");
                percent.textContent = `${score}%`;

                node.append(rank, title, percent);
                profileKnowledgeMap.appendChild(node);
            });
        }
    }

    if (profileTopicList) {
        profileTopicList.replaceChildren();
        const topics = data.topics || [];

        if (!topics.length) {
            profileTopicList.appendChild(createProfileEmpty("Темы появятся после первого вопроса."));
        } else {
            topics.forEach((topic) => {
                const item = document.createElement("article");
                item.className = "profile-topic";

                const row = document.createElement("div");
                const title = document.createElement("strong");
                title.textContent = topic.title || "Тема";
                const meta = document.createElement("span");
                meta.className = `rank-pill ${rankClassName(topic.rank)}`;
                meta.textContent = `${topic.rank || "Coal"}, ${topic.score || 0}%`;
                row.append(title, meta);

                const bar = document.createElement("div");
                bar.className = "profile-mini-bar";
                bar.setAttribute("aria-hidden", "true");
                const fill = document.createElement("span");
                fill.style.width = `${Number(topic.score || 0)}%`;
                bar.appendChild(fill);

                item.append(row, bar);
                profileTopicList.appendChild(item);
            });
        }
    }

    if (profileCardList) {
        profileCardList.replaceChildren();
        const cards = data.cards || [];

        if (!cards.length) {
            profileCardList.appendChild(createProfileEmpty("Карточки сохранятся из ответов бота."));
        } else {
            cards.forEach((card) => {
                const item = document.createElement("article");
                item.className = "profile-card-item";

                const topic = document.createElement("span");
                topic.textContent = card.topic || "Тема";
                const front = document.createElement("strong");
                front.textContent = card.front || "Карточка";
                const back = document.createElement("p");
                back.textContent = card.back || "";

                item.append(topic, front, back);
                profileCardList.appendChild(item);
            });
        }
    }
}

async function refreshProfile() {
    try {
        const response = await fetch("/profile");
        const data = await response.json().catch(() => null);

        if (response.ok) {
            renderProfile(data);
        }
    } catch (error) {
        setStatus("Не удалось обновить профиль");
        setTimeout(() => setStatus(""), 1800);
    }
}

function showProfile() {
    profileModal?.classList.add("open");
    profileModal?.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    refreshProfile();
}

function hideProfile() {
    profileModal?.classList.remove("open");
    profileModal?.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
}

function renderGameSkeleton() {
    gameArea.replaceChildren();

    const shell = document.createElement("section");
    shell.className = "game-shell game-skeleton";
    shell.setAttribute("aria-label", "Мини-игра загружается");

    const header = document.createElement("div");
    header.className = "game-header";

    const title = document.createElement("span");
    title.className = "skeleton-line skeleton-title";

    const intro = document.createElement("span");
    intro.className = "skeleton-line skeleton-medium";

    header.append(title, intro);

    const cards = document.createElement("div");
    cards.className = "skeleton-card-list";

    for (let index = 0; index < 3; index += 1) {
        const card = document.createElement("div");
        card.className = "skeleton-game-card";

        const lineA = document.createElement("span");
        lineA.className = "skeleton-line";
        lineA.style.width = `${86 - index * 10}%`;

        const lineB = document.createElement("span");
        lineB.className = "skeleton-line skeleton-small";

        card.append(lineA, lineB);
        cards.appendChild(card);
    }

    shell.append(header, cards);
    gameArea.appendChild(shell);
}

function setLoadingState(active) {
    isAsking = active;
    chatForm?.querySelector("input[name='topic']")?.toggleAttribute("disabled", active);
    chatForm?.querySelector("button[type='submit']")?.toggleAttribute("disabled", active);
    modeButtons.forEach((button) => button.toggleAttribute("disabled", active));
    syncGameChoices();
    syncGameButton();
}

function activateMode(button) {
    modeButtons.forEach((mode) => mode.classList.remove("active"));
    button.classList.add("active");
    modeSelect.value = button.dataset.value;
}

function normalizeAnswer(value) {
    return String(value || "")
        .trim()
        .toLowerCase()
        .replaceAll("ё", "е")
        .replace(/[.,!?;:()[\]{}"«»]/g, "")
        .replace(/\s+/g, " ");
}

function shuffle(items) {
    return [...items].sort(() => Math.random() - 0.5);
}

function createGameShell(game) {
    gameArea.replaceChildren();

    const shell = document.createElement("section");
    shell.className = "game-shell";

    const header = document.createElement("div");
    header.className = "game-header";

    const title = document.createElement("h4");
    title.textContent = game.title || "Мини-игра";

    const intro = document.createElement("p");
    intro.textContent = game.intro || "Проверь, как улеглась мысль.";

    header.append(title, intro);

    const content = document.createElement("div");
    content.className = "game-content";

    shell.append(header, content);
    gameArea.appendChild(shell);

    return content;
}

function createFeedbackNode() {
    const feedback = document.createElement("div");
    feedback.className = "game-feedback";
    feedback.setAttribute("aria-live", "polite");
    return feedback;
}

function replayClass(element, className) {
    if (!element) {
        return;
    }

    element.classList.remove(className);
    void element.offsetWidth;
    element.classList.add(className);
}

function celebrateSuccess(target) {
    const container = target?.closest(".quiz-card, .blank-task, .sentence-builder, .choice-options, .game-shell") || gameArea;

    if (!container) {
        return;
    }

    container.classList.add("celebration-host");

    const burst = document.createElement("div");
    burst.className = "confetti-burst";
    burst.setAttribute("aria-hidden", "true");

    for (let index = 0; index < 14; index += 1) {
        const piece = document.createElement("i");
        const angle = (Math.PI * 2 * index) / 14;
        const distance = 46 + Math.random() * 42;
        const x = Math.cos(angle) * distance;
        const y = Math.sin(angle) * distance;
        const rotation = Math.round(Math.random() * 220 - 110);

        piece.style.setProperty("--x", `${x}px`);
        piece.style.setProperty("--y", `${y}px`);
        piece.style.setProperty("--r", `${rotation}deg`);
        piece.style.animationDelay = `${Math.random() * 70}ms`;
        burst.appendChild(piece);
    }

    container.appendChild(burst);
    setTimeout(() => burst.remove(), 980);
}

function showMistake(target) {
    const element = target?.closest(".quiz-card, .blank-task, .sentence-builder, .choice-card") || target;
    replayClass(element, "mistake-shake");
}

modeButtons.forEach((button) => {
    button.addEventListener("click", () => activateMode(button));
});

if (modeButtons.length > 0 && modeSelect) {
    activateMode(modeButtons[0]);
}

gameChoiceButtons.forEach((button) => {
    button.addEventListener("click", () => {
        if (button.disabled || button.classList.contains("completed")) {
            return;
        }

        selectedGameType = button.dataset.gameType || "true_false";
        gameChoiceButtons.forEach((choice) => choice.classList.remove("active"));
        button.classList.add("active");
    });
});

recentTopicList?.addEventListener("click", (event) => {
    const button = event.target.closest(".recent-topic");

    if (!button) {
        return;
    }

    const input = getTopicInput();
    input.value = button.dataset.topic || button.textContent || "";
    input.focus();
});

chatForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const input = getTopicInput();
    const topic = input.value.trim();
    const mode = modeSelect.value;

    if (!topic || isAsking) {
        return;
    }

    removeEmptyState();
    gameArea.replaceChildren();
    setLoadingState(true);
    setStatus("Отправляю запрос...");

    chatMessages.appendChild(createUserMessage(topic, mode));
    input.value = "";

    const loadingMessage = createAssistantSkeleton();
    chatMessages.appendChild(loadingMessage);
    scrollChatToBottom();

    try {
        const response = await fetch("/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ topic, mode }),
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            clearMessageSkeleton(loadingMessage);
            loadingMessage.querySelector(".message-body").textContent = data.error || "Ошибка ответа от сервера";
            setStatus("");
            return;
        }

        if (!data.answer) {
            clearMessageSkeleton(loadingMessage);
            loadingMessage.querySelector(".message-body").textContent = "Ошибка: пустой ответ";
            setStatus("");
            return;
        }

        clearMessageSkeleton(loadingMessage);
        renderRecentTopics(data.recentTopics || []);
        updateProgressCard(data.progress);
        gameArea.replaceChildren();
        setStatus("Печатаю ответ...");
        await typeAssistantMessage(loadingMessage, data.answer);
        hasAnswer = true;
        setStatus("Готово");
        setTimeout(() => setStatus(""), 1600);
        scrollChatToBottom();
    } catch (error) {
        clearMessageSkeleton(loadingMessage);
        loadingMessage.querySelector(".message-body").textContent = "Ошибка сети";
        setStatus("");
    } finally {
        setLoadingState(false);
        input.focus();
    }
});

gameBtn?.addEventListener("click", async () => {
    if (!hasAnswer || isGameLoading) {
        return;
    }

    isGameLoading = true;
    syncGameButton();
    gameChoiceButtons.forEach((button) => button.disabled = true);
    renderGameSkeleton();
    setStatus("Генерирую игру...");

    try {
        const response = await fetch("/game", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: selectedGameType, topic: lastAnswerTopic }),
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            renderGameError(data.error || "Ошибка генерации игры");
            updateProgressCard(data.progress);
            return;
        }

        renderGame(data.game);
        setStatus("");
    } catch (error) {
        renderGameError("Ошибка запроса");
    } finally {
        isGameLoading = false;
        syncGameChoices();
    }
});

function renderGameError(message) {
    const errorNode = document.createElement("div");
    errorNode.className = "quiz-card";
    errorNode.textContent = message;
    gameArea.replaceChildren(errorNode);
    setStatus("");
}

function renderGame(game) {
    if (!game || !game.type) {
        renderGameError("Ошибка: пустая игра");
        return;
    }

    const renderers = {
        true_false: renderTrueFalseGame,
        fill_blank: renderFillBlankGame,
        sentence_order: renderSentenceOrderGame,
        simple_choice: renderSimpleChoiceGame,
    };

    const renderer = renderers[game.type];

    if (!renderer) {
        renderGameError("Такой тип игры пока не поддерживается");
        return;
    }

    renderer(game);
}

function renderTrueFalseGame(game) {
    const content = createGameShell(game);
    const list = document.createElement("div");
    list.className = "quiz-list";
    let answeredCount = 0;

    game.items.forEach((item) => {
        let progressReported = false;
        const card = document.createElement("article");
        card.className = "quiz-card";

        const text = document.createElement("p");
        text.textContent = item.text || "Утверждение без текста";

        const actions = document.createElement("div");
        actions.className = "quiz-actions";

        const trueButton = document.createElement("button");
        trueButton.className = "btn btn-true";
        trueButton.type = "button";
        trueButton.textContent = "Верно";

        const falseButton = document.createElement("button");
        falseButton.className = "btn btn-false";
        falseButton.type = "button";
        falseButton.textContent = "Не так";

        const hintButton = document.createElement("button");
        hintButton.className = "btn btn-ghost";
        hintButton.type = "button";
        hintButton.textContent = "Подсказка";

        const result = document.createElement("div");
        result.className = "quiz-result";

        function answer(userAnswer) {
            if (progressReported) {
                return;
            }

            const correct = Boolean(item.correct);
            const isRight = userAnswer === correct;
            progressReported = true;
            answeredCount += 1;
            result.textContent = isRight
                ? `Правильно. ${item.explanation || "Ты держишь главный смысл."}`
                : `Не страшно. ${item.explanation || "Тут была маленькая ловушка в формулировке."}`;
            result.classList.toggle("success", isRight);
            result.classList.toggle("danger", !isRight);
            trueButton.disabled = true;
            falseButton.disabled = true;

            if (isRight) {
                celebrateSuccess(card);
            } else {
                showMistake(card);
            }

            reportGameResult(isRight, game.type, answeredCount >= game.items.length);
        }

        trueButton.addEventListener("click", () => answer(true));
        falseButton.addEventListener("click", () => answer(false));
        hintButton.addEventListener("click", () => {
            result.textContent = item.hint || "Ищи слова, которые делают утверждение слишком абсолютным.";
        });

        actions.append(trueButton, falseButton, hintButton);
        card.append(text, actions, result);
        list.appendChild(card);
    });

    content.appendChild(list);
}

function renderFillBlankGame(game) {
    const content = createGameShell(game);
    const selected = Array(game.answers.length).fill(null);
    const selectedChipIndexes = Array(game.answers.length).fill(null);
    let progressReported = false;

    const task = document.createElement("div");
    task.className = "blank-task";

    const phrase = document.createElement("div");
    phrase.className = "blank-phrase";

    const slots = [];
    game.textParts.forEach((part, index) => {
        phrase.appendChild(document.createTextNode(part));

        if (index < game.answers.length) {
            const slot = document.createElement("button");
            slot.className = "blank-slot";
            slot.type = "button";
            slot.textContent = "___";
            slot.addEventListener("click", () => clearSlot(index));
            slots.push(slot);
            phrase.appendChild(slot);
        }
    });

    const bank = document.createElement("div");
    bank.className = "word-bank";

    shuffle(game.wordBank).forEach((word, chipIndex) => {
        const chip = document.createElement("button");
        chip.className = "word-chip";
        chip.type = "button";
        chip.textContent = word;
        chip.dataset.index = String(chipIndex);
        chip.addEventListener("click", () => fillFirstEmpty(word, chipIndex));
        bank.appendChild(chip);
    });

    const actions = document.createElement("div");
    actions.className = "quiz-actions";

    const checkButton = document.createElement("button");
    checkButton.className = "btn btn-secondary";
    checkButton.type = "button";
    checkButton.textContent = "Проверить";

    const hintButton = document.createElement("button");
    hintButton.className = "btn btn-ghost";
    hintButton.type = "button";
    hintButton.textContent = "Подсказка";

    const resetButton = document.createElement("button");
    resetButton.className = "btn btn-ghost";
    resetButton.type = "button";
    resetButton.textContent = "Сбросить";

    const feedback = createFeedbackNode();

    function chipByIndex(chipIndex) {
        return bank.querySelector(`[data-index="${chipIndex}"]`);
    }

    function clearSlot(slotIndex) {
        const chipIndex = selectedChipIndexes[slotIndex];
        if (chipIndex !== null) {
            chipByIndex(chipIndex)?.removeAttribute("disabled");
        }

        selected[slotIndex] = null;
        selectedChipIndexes[slotIndex] = null;
        slots[slotIndex].textContent = "___";
        slots[slotIndex].classList.remove("wrong", "filled");
        feedback.textContent = "";
    }

    function fillFirstEmpty(word, chipIndex) {
        const targetIndex = selected.findIndex((value) => value === null);

        if (targetIndex === -1) {
            feedback.textContent = "Все места уже заняты. Нажми на пропуск, если хочешь заменить слово.";
            return;
        }

        selected[targetIndex] = word;
        selectedChipIndexes[targetIndex] = chipIndex;
        slots[targetIndex].textContent = word;
        slots[targetIndex].classList.add("filled");
        slots[targetIndex].classList.remove("wrong");
        chipByIndex(chipIndex)?.setAttribute("disabled", "true");
        feedback.textContent = "";
    }

    checkButton.addEventListener("click", () => {
        let isCorrect = true;

        selected.forEach((value, index) => {
            const accepted = game.answers[index].map(normalizeAnswer);
            const matches = accepted.includes(normalizeAnswer(value));
            slots[index].classList.toggle("wrong", !matches);

            if (!matches) {
                isCorrect = false;
            }
        });

        if (selected.some((value) => value === null)) {
            feedback.textContent = "Заполни все пропуски, и мы вместе проверим.";
            feedback.className = "game-feedback";
            return;
        }

        feedback.textContent = isCorrect ? game.success : game.feedback;
        feedback.className = `game-feedback ${isCorrect ? "success" : "danger"}`;

        if (isCorrect) {
            celebrateSuccess(task);
        } else {
            showMistake(task);
        }

        if (!progressReported) {
            progressReported = true;
            reportGameResult(isCorrect, game.type, true);
        }
    });

    hintButton.addEventListener("click", () => {
        feedback.textContent = game.hint || "Выбирай слова, без которых смысл объяснения разваливается.";
        feedback.className = "game-feedback";
    });

    resetButton.addEventListener("click", () => {
        selected.forEach((_, index) => clearSlot(index));
    });

    actions.append(checkButton, hintButton, resetButton);
    task.append(phrase, bank, actions, feedback);
    content.appendChild(task);
}

function renderSentenceOrderGame(game) {
    const content = createGameShell(game);
    const selectedIds = [];
    let progressReported = false;

    const builder = document.createElement("div");
    builder.className = "sentence-builder";

    const answerRow = document.createElement("div");
    answerRow.className = "sentence-answer";

    const bank = document.createElement("div");
    bank.className = "fragment-bank";

    const actions = document.createElement("div");
    actions.className = "quiz-actions";

    const checkButton = document.createElement("button");
    checkButton.className = "btn btn-secondary";
    checkButton.type = "button";
    checkButton.textContent = "Проверить";

    const hintButton = document.createElement("button");
    hintButton.className = "btn btn-ghost";
    hintButton.type = "button";
    hintButton.textContent = "Подсказка";

    const resetButton = document.createElement("button");
    resetButton.className = "btn btn-ghost";
    resetButton.type = "button";
    resetButton.textContent = "Сбросить";

    const feedback = createFeedbackNode();
    const fragmentsById = new Map(game.fragments.map((fragment) => [fragment.id, fragment]));
    const shuffledFragments = shuffle(game.fragments);

    function renderRows() {
        answerRow.replaceChildren();
        bank.replaceChildren();

        if (selectedIds.length === 0) {
            const placeholder = document.createElement("span");
            placeholder.className = "sentence-placeholder";
            placeholder.textContent = "Нажимай фрагменты снизу";
            answerRow.appendChild(placeholder);
        }

        selectedIds.forEach((id, index) => {
            const chip = document.createElement("button");
            chip.className = "fragment-chip selected";
            chip.type = "button";
            chip.textContent = fragmentsById.get(id)?.text || id;
            chip.addEventListener("click", () => {
                selectedIds.splice(index, 1);
                feedback.textContent = "";
                renderRows();
            });
            answerRow.appendChild(chip);
        });

        shuffledFragments.forEach((fragment) => {
            if (selectedIds.includes(fragment.id)) {
                return;
            }

            const chip = document.createElement("button");
            chip.className = "fragment-chip";
            chip.type = "button";
            chip.textContent = fragment.text;
            chip.addEventListener("click", () => {
                selectedIds.push(fragment.id);
                feedback.textContent = "";
                renderRows();
            });
            bank.appendChild(chip);
        });
    }

    checkButton.addEventListener("click", () => {
        if (selectedIds.length !== game.order.length) {
            feedback.textContent = "Собери все фрагменты, потом проверим.";
            feedback.className = "game-feedback";
            return;
        }

        const isCorrect = selectedIds.every((id, index) => id === game.order[index]);
        feedback.className = `game-feedback ${isCorrect ? "success" : "danger"}`;

        if (isCorrect) {
            const sentence = game.order.map((id) => fragmentsById.get(id)?.text || "").join(" ");
            feedback.textContent = `${game.success} ${sentence}`;
            celebrateSuccess(builder);
        } else {
            feedback.textContent = game.feedback;
            showMistake(builder);
        }

        if (!progressReported) {
            progressReported = true;
            reportGameResult(isCorrect, game.type, true);
        }
    });

    hintButton.addEventListener("click", () => {
        feedback.textContent = game.hint || "Начни с главного понятия, потом добавь, что оно делает.";
        feedback.className = "game-feedback";
    });

    resetButton.addEventListener("click", () => {
        selectedIds.splice(0, selectedIds.length);
        feedback.textContent = "";
        renderRows();
    });

    actions.append(checkButton, hintButton, resetButton);
    builder.append(answerRow, bank, actions, feedback);
    content.appendChild(builder);
    renderRows();
}

function renderSimpleChoiceGame(game) {
    const content = createGameShell(game);
    let progressReported = false;
    const question = document.createElement("p");
    question.className = "choice-question";
    question.textContent = game.question;

    const options = document.createElement("div");
    options.className = "choice-options";

    const feedback = createFeedbackNode();
    const hintButton = document.createElement("button");
    hintButton.className = "btn btn-ghost";
    hintButton.type = "button";
    hintButton.textContent = "Подсказка";
    hintButton.addEventListener("click", () => {
        feedback.textContent = game.hint || "Лучший ответ простой, но не теряет главный нюанс.";
        feedback.className = "game-feedback";
    });

    game.options.forEach((option) => {
        const card = document.createElement("button");
        card.className = "choice-card";
        card.type = "button";
        card.textContent = option.text;

        card.addEventListener("click", () => {
            const isBest = Boolean(option.isBest);
            card.classList.toggle("correct", isBest);
            card.classList.toggle("wrong", !isBest);
            feedback.className = `game-feedback ${isBest ? "success" : "danger"}`;
            feedback.textContent = isBest ? `${game.success} ${option.feedback}` : option.feedback;

            if (!progressReported) {
                progressReported = true;
                reportGameResult(isBest, game.type, true);
            }

            if (isBest) {
                celebrateSuccess(card);
                options.querySelectorAll(".choice-card").forEach((item) => item.disabled = true);
            } else {
                showMistake(card);
            }
        });

        options.appendChild(card);
    });

    content.append(question, options, hintButton, feedback);
}

document.querySelectorAll(".faq-item").forEach((item) => {
    const button = item.querySelector(".faq-question");
    const indicator = button?.querySelector("span");

    button?.addEventListener("click", () => {
        const isOpen = item.classList.toggle("open");
        button.setAttribute("aria-expanded", String(isOpen));

        if (indicator) {
            indicator.textContent = isOpen ? "−" : "+";
        }
    });
});

openProfile?.addEventListener("click", showProfile);
closeProfile?.addEventListener("click", hideProfile);
profileModal?.addEventListener("click", (event) => {
    if (event.target.matches("[data-profile-close]")) {
        hideProfile();
    }
});
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && profileModal?.classList.contains("open")) {
        hideProfile();
    }
});

resetChat?.addEventListener("click", async () => {
    resetChat.disabled = true;
    setStatus("Очищаю чат...");

    try {
        const response = await fetch("/reset", { method: "POST" });

        if (!response.ok) {
            setStatus("Не удалось очистить чат");
            return;
        }

        hasAnswer = false;
        gameArea.replaceChildren();
        chatMessages.replaceChildren();
        renderRecentTopics([]);
        updateProgressCard({ topic: "Тема не выбрана", score: 0, rank: "Coal", completedGames: [] });

        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.id = "emptyState";

        const title = document.createElement("strong");
        title.textContent = "Готов к разбору.";

        const text = document.createElement("span");
        text.textContent = "Напиши любую тему ниже.";

        empty.append(title, text);
        chatMessages.appendChild(empty);
        setStatus("");
        syncGameButton();
    } catch (error) {
        setStatus("Ошибка сети");
    } finally {
        resetChat.disabled = false;
    }
});

syncGameChoices();
scrollChatToBottom();
