/*
  The app's own dialogs, in place of the browser's confirm, alert and prompt.

  Most visits are filed from a phone, often from the installed app. There the
  browser's boxes freeze the page, cannot be styled, and are titled with the
  site's address. These ask the same three questions in a native <dialog>:
  the app's look, Escape and the phone's back gesture to dismiss, focus kept
  inside while it is open and handed back afterwards.

  They answer with a promise, so a caller waits for the answer:

      if (!await uiConfirm('Delete this comment?', { ok: 'Delete', danger: true })) return;
      await uiAlert('Could not save.');
      const note = await uiPrompt('What was fixed?');   // null when cancelled

  One question at a time: a second waits until the first is answered. The
  message is set as text, never as HTML, because it often carries a person's
  or a community's name.

  uiOpen() / uiClose() / uiIsOpen() open and close the pages' own <dialog>s
  the same way. showModal() is missing only from very old browsers and from
  jsdom; there the dialog is shown with the open attribute instead.
*/
(function () {
    function uiOpen(d) {
        if (!d || d.hasAttribute('open')) return;
        if (typeof d.showModal === 'function') d.showModal();
        else d.setAttribute('open', '');
    }

    function uiClose(d, value) {
        if (!d || !d.hasAttribute('open')) return;
        if (typeof d.close === 'function') { d.close(value); return; }
        d.returnValue = value || '';
        d.removeAttribute('open');
        d.dispatchEvent(new Event('close'));
    }

    function uiIsOpen(d) {
        return !!(d && d.hasAttribute('open'));
    }

    function button(label, cls, value, d) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'ui-dialog-btn ' + cls;
        b.textContent = label;
        b.addEventListener('click', () => uiClose(d, value));
        return b;
    }

    // kind: 'alert' | 'confirm' | 'prompt'
    function show(kind, message, opts) {
        opts = opts || {};
        return new Promise(resolve => {
            const d = document.createElement('dialog');
            d.className = 'ui-dialog';
            const msg = document.createElement('p');
            msg.className = 'ui-dialog-msg';
            msg.id = 'uiDialogMsg' + Date.now().toString(36);
            msg.textContent = String(message == null ? '' : message);
            d.setAttribute('aria-labelledby', msg.id);
            d.appendChild(msg);

            let input = null;
            if (kind === 'prompt') {
                input = document.createElement('input');
                input.type = 'text';
                input.className = 'ui-dialog-input';
                input.value = opts.value == null ? '' : String(opts.value);
                input.setAttribute('aria-labelledby', msg.id);
                // Enter answers, as it did in prompt(). Not while an input
                // method is still composing a word: that Enter picks the word.
                input.addEventListener('keydown', e => {
                    if (e.key === 'Enter' && !e.isComposing && e.keyCode !== 229) {
                        e.preventDefault();
                        uiClose(d, 'ok');
                    }
                });
                d.appendChild(input);
            }

            const row = document.createElement('div');
            row.className = 'ui-dialog-actions';
            let cancel = null;
            if (kind !== 'alert') {
                cancel = button(opts.cancel || 'Cancel', 'ui-dialog-cancel', '', d);
                row.appendChild(cancel);
            }
            const ok = button(opts.ok || 'OK', opts.danger ? 'ui-dialog-danger' : 'ui-dialog-ok', 'ok', d);
            row.appendChild(ok);
            d.appendChild(row);

            d.addEventListener('close', () => {
                const yes = d.returnValue === 'ok';
                const typed = input ? input.value : null;
                d.remove();
                if (kind === 'confirm') resolve(yes);
                else if (kind === 'prompt') resolve(yes ? typed : null);
                else resolve();
            }, { once: true });

            document.body.appendChild(d);
            uiOpen(d);
            // A destructive question starts on the safe answer.
            const first = input || (opts.danger && cancel) || ok;
            first.focus();
            if (input) input.select();
        });
    }

    let queue = Promise.resolve();
    function ask(kind, message, opts) {
        const answer = queue.then(() => show(kind, message, opts));
        queue = answer.catch(() => {});
        return answer;
    }

    window.uiOpen = uiOpen;
    window.uiClose = uiClose;
    window.uiIsOpen = uiIsOpen;
    window.uiAlert = (message, opts) => ask('alert', message, opts);
    window.uiConfirm = (message, opts) => ask('confirm', message, opts);
    window.uiPrompt = (message, value, opts) =>
        ask('prompt', message, Object.assign({}, opts, { value }));
})();
