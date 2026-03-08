/**
 * Like Reactions – Progressive animation & funny bilingual messages
 * Keeps users tapping with escalating encouragement & heart explosions
 */
(function () {
    'use strict';

    /* ── Bilingual message tiers ─────────────────────────── */
    const MESSAGES = {
        en: [
            /* 1  */ "Tap again! 👀",
            /* 2  */ "Keep going! 💪",
            /* 3  */ "You're on fire! 🔥",
            /* 4  */ "Don't stop now! 😤",
            /* 5  */ "Is your finger ok? 😂",
            /* 6  */ "BEAST MODE 🦁",
            /* 7  */ "The author felt that! 💥",
            /* 8  */ "You broke our servers! 💀",
            /* 9  */ "OK relax champion 🏆",
            /* 10 */ "Legend. Absolute legend. 👑",
            /* 11+*/ "Certified tap addict 😵‍💫",
        ],
        fr: [
            /* 1  */ "Tape encore ! 👀",
            /* 2  */ "Continue ! 💪",
            /* 3  */ "T'es en feu ! 🔥",
            /* 4  */ "Arrête pas ! 😤",
            /* 5  */ "Ton doigt va bien ? 😂",
            /* 6  */ "MODE BÊTE 🦁",
            /* 7  */ "L'auteur a senti ça ! 💥",
            /* 8  */ "Tu as cassé nos serveurs ! 💀",
            /* 9  */ "OK relax champion 🏆",
            /* 10 */ "Légende. Absolue légende. 👑",
            /* 11+*/ "Accro au tap certifié 😵‍💫",
        ],
    };

    const HEART_EMOJIS = ['❤️', '🧡', '💛', '💚', '💙', '💜', '🩷', '🩵', '💖', '💗', '💓', '💞', '✨', '⭐', '🌟'];

    /* ── State ────────────────────────────────────────────── */
    let tapCount = 0;
    let lastTapTime = 0;
    let comboTimer = null;
    let toastEl = null;

    /* ── Detect language ──────────────────────────────────── */
    function getLang() {
        const html = document.documentElement.lang || '';
        return html.startsWith('fr') ? 'fr' : 'en';
    }

    /* ── Get message for current tier ─────────────────────── */
    function getMessage(count) {
        const msgs = MESSAGES[getLang()] || MESSAGES.en;
        const idx = Math.min(count - 1, msgs.length - 1);
        return msgs[idx];
    }

    /* ── Toast bubble ─────────────────────────────────────── */
    function showToast(text, intensity) {
        if (!toastEl) {
            toastEl = document.createElement('div');
            toastEl.id = 'like-toast';
            document.body.appendChild(toastEl);
        }

        // Style based on intensity (0-1)
        const hue = 340 + intensity * 30;        // shift from pink→red→orange
        const scale = 1 + intensity * 0.15;       // slightly bigger at higher combos
        const bg = `hsl(${hue}, 85%, ${40 - intensity * 10}%)`;

        Object.assign(toastEl.style, {
            position: 'fixed',
            bottom: '140px',
            left: '50%',
            transform: `translateX(-50%) scale(${scale})`,
            padding: '10px 20px',
            borderRadius: '999px',
            background: bg,
            color: '#fff',
            fontSize: '14px',
            fontWeight: '700',
            fontFamily: "'Inter', -apple-system, sans-serif",
            zIndex: '9999',
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            boxShadow: `0 4px 24px ${bg}66`,
            opacity: '0',
            transition: 'none',
            letterSpacing: '0.3px',
        });

        toastEl.textContent = text;

        // Trigger reflow then animate in
        void toastEl.offsetWidth;
        Object.assign(toastEl.style, {
            transition: 'opacity 0.15s ease, transform 0.25s cubic-bezier(0.34,1.56,0.64,1)',
            opacity: '1',
            transform: `translateX(-50%) scale(${scale})`,
        });

        // Fade out after delay (shorter at higher intensity for rapid tapping)
        clearTimeout(toastEl._fadeTimer);
        const duration = Math.max(800, 1800 - intensity * 800);
        toastEl._fadeTimer = setTimeout(() => {
            if (toastEl) {
                toastEl.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                toastEl.style.opacity = '0';
                toastEl.style.transform = `translateX(-50%) scale(0.8) translateY(10px)`;
            }
        }, duration);
    }

    /* ── Particle explosion ───────────────────────────────── */
    function spawnParticles(iconEl, count) {
        const rect = iconEl.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;

        for (let i = 0; i < count; i++) {
            const p = document.createElement('span');
            p.textContent = HEART_EMOJIS[Math.floor(Math.random() * HEART_EMOJIS.length)];
            const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.6;
            const dist = 30 + Math.random() * 50 + count * 3;
            const size = 12 + Math.random() * 10 + Math.min(count, 8);

            Object.assign(p.style, {
                position: 'fixed',
                left: cx + 'px',
                top: cy + 'px',
                fontSize: size + 'px',
                pointerEvents: 'none',
                zIndex: '9998',
                transition: 'none',
                opacity: '1',
                transform: 'translate(-50%, -50%) scale(0)',
            });

            document.body.appendChild(p);

            // Animate out
            requestAnimationFrame(() => {
                const dx = Math.cos(angle) * dist;
                const dy = Math.sin(angle) * dist - 20; // bias upward
                const rot = (Math.random() - 0.5) * 120;
                const dur = 0.5 + Math.random() * 0.3;

                p.style.transition = `all ${dur}s cubic-bezier(0.25, 1, 0.5, 1)`;
                p.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(1) rotate(${rot}deg)`;
                p.style.opacity = '0';
            });

            setTimeout(() => p.remove(), 1000);
        }
    }

    /* ── Button pulse/shake animation (CSS class based) ──── */
    function animateButton(iconEl, intensity) {
        // Remove previous animation class
        iconEl.classList.remove('like-pop-1', 'like-pop-2', 'like-pop-3');
        void iconEl.offsetWidth;

        // Choose animation tier
        if (intensity < 0.3) {
            iconEl.classList.add('like-pop-1');
        } else if (intensity < 0.7) {
            iconEl.classList.add('like-pop-2');
        } else {
            iconEl.classList.add('like-pop-3');
        }

        // Color flash – more intense = more vivid
        const hue = 340 + intensity * 40;
        iconEl.style.background = `hsl(${hue}, 80%, ${90 - intensity * 25}%)`;
        setTimeout(() => {
            iconEl.style.transition = 'background 0.6s ease';
            iconEl.style.background = '';
            setTimeout(() => { iconEl.style.transition = ''; }, 600);
        }, 200);
    }

    /* ── Counter bounce ───────────────────────────────────── */
    function animateCounter(countEl) {
        countEl.style.transition = 'none';
        countEl.style.transform = 'scale(1.4)';
        countEl.style.color = '#722F37';
        void countEl.offsetWidth;
        countEl.style.transition = 'transform 0.3s cubic-bezier(0.34,1.56,0.64,1), color 0.5s ease';
        countEl.style.transform = 'scale(1)';
        setTimeout(() => { countEl.style.color = ''; }, 500);
    }

    /* ── Main handler ─────────────────────────────────────── */
    window.likeArticle = function (articleId) {
        const countEl = document.getElementById('like-count');
        const iconEl = document.getElementById('like-icon');
        if (!countEl || !iconEl) return;

        const now = Date.now();
        const timeSinceLast = now - lastTapTime;
        lastTapTime = now;

        // Reset combo if user waited too long (>3s)
        if (timeSinceLast > 3000) tapCount = 0;
        tapCount++;

        // Intensity ramps from 0→1 over taps 1→10
        const intensity = Math.min(1, (tapCount - 1) / 9);

        // Update count optimistically
        const currentCount = parseInt(countEl.textContent) || 0;
        countEl.textContent = currentCount + 1;

        // ── Animations ──
        // 1. Button animation (scales with intensity)
        animateButton(iconEl, intensity);

        // 2. Counter bounce
        animateCounter(countEl);

        // 3. Particles (more at higher combos)
        const particleCount = Math.min(2 + Math.floor(tapCount * 1.5), 18);
        spawnParticles(iconEl, particleCount);

        // 4. Show funny message (after first tap)
        if (tapCount >= 1) {
            showToast(getMessage(tapCount), intensity);
        }

        // Reset combo after inactivity
        clearTimeout(comboTimer);
        comboTimer = setTimeout(() => { tapCount = 0; }, 3000);

        // ── API call ──
        fetch(`/api/blog/${articleId}/like/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value
                    || document.cookie.match(/csrftoken=([^;]+)/)?.[1]
                    || '',
                'Content-Type': 'application/json',
            },
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) countEl.textContent = data.likes;
            })
            .catch(() => {
                countEl.textContent = currentCount;
            });
    };
})();
