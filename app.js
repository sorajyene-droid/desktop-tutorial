const STORAGE_KEY = "todo-app:todos";

const form = document.getElementById("todo-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const countEl = document.getElementById("count");
const clearBtn = document.getElementById("clear-completed");
const filterBtns = document.querySelectorAll(".filter-btn");

let todos = loadTodos();
let currentFilter = "all";

function loadTodos() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveTodos() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
}

function addTodo(text) {
  todos.push({
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    text,
    completed: false,
  });
  saveTodos();
  render();
}

function toggleTodo(id) {
  const todo = todos.find((t) => t.id === id);
  if (todo) {
    todo.completed = !todo.completed;
    saveTodos();
    render();
  }
}

function deleteTodo(id) {
  todos = todos.filter((t) => t.id !== id);
  saveTodos();
  render();
}

function clearCompleted() {
  todos = todos.filter((t) => !t.completed);
  saveTodos();
  render();
}

function getFiltered() {
  switch (currentFilter) {
    case "active":
      return todos.filter((t) => !t.completed);
    case "completed":
      return todos.filter((t) => t.completed);
    default:
      return todos;
  }
}

function render() {
  const filtered = getFiltered();
  list.innerHTML = "";

  if (filtered.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent =
      currentFilter === "all"
        ? "やることはまだありません"
        : "該当する項目はありません";
    list.appendChild(empty);
  } else {
    for (const todo of filtered) {
      list.appendChild(createTodoElement(todo));
    }
  }

  const remaining = todos.filter((t) => !t.completed).length;
  countEl.textContent = `未完了: ${remaining} 件`;
}

function createTodoElement(todo) {
  const li = document.createElement("li");
  li.className = "todo-item" + (todo.completed ? " completed" : "");

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = todo.completed;
  checkbox.addEventListener("change", () => toggleTodo(todo.id));

  const text = document.createElement("span");
  text.className = "todo-text";
  text.textContent = todo.text;

  const delBtn = document.createElement("button");
  delBtn.className = "delete-btn";
  delBtn.type = "button";
  delBtn.setAttribute("aria-label", "削除");
  delBtn.textContent = "×";
  delBtn.addEventListener("click", () => deleteTodo(todo.id));

  li.append(checkbox, text, delBtn);
  return li;
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addTodo(text);
  input.value = "";
  input.focus();
});

clearBtn.addEventListener("click", clearCompleted);

filterBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    currentFilter = btn.dataset.filter;
    filterBtns.forEach((b) => b.classList.toggle("active", b === btn));
    render();
  });
});

render();
