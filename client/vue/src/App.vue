<script setup lang="ts">
import { onBeforeUnmount, onMounted, provide, ref } from 'vue';
import { Button } from '@syncfusion/ej2-buttons';
import { Tooltip } from '@syncfusion/ej2-popups';
import { SpreadsheetComponent as EjsSpreadsheet } from '@syncfusion/ej2-vue-spreadsheet';
import { CollaborativeEditingHandler, type Spreadsheet } from '@syncfusion/ej2-spreadsheet';
import { CollaborationClient } from '@syncfusion/ej2-collaborator';
import { SpreadsheetEditorAdapter } from './SpreadsheetEditorAdapter';

const serviceUrl: string = 'YOUR_COLLABORATION_SERVER_URL';

const userNames: string[] = [
    'James Carter', 'Olivia Bennett', 'William Parker', 'Emma Collins',
    'Henry Mitchell', 'Amelia Foster', 'Benjamin Turner', 'Charlotte Morgan',
    'Lucas Anderson', 'Sophia Reynolds', 'Alexander Brooks', 'Isabella Hayes',
    'Daniel Cooper', 'Mia Richardson', 'Matthew Hughes', 'Evelyn Ward',
    'Samuel Peterson', 'Harper Jenkins', 'Joseph Sanders', 'Camila Bryant',
    'David Russell', 'Luna Griffin', 'Michael Perry', 'Sofia Coleman',
    'Ethan Powell', 'Avery Patterson', 'John Sullivan', 'Elizabeth Murphy',
    'Jack Hamilton', 'Eleanor Wallace', 'Owen Simmons', 'Abigail Butler',
    'Luke Henderson', 'Ella Fisher', 'Thomas Graham', 'Scarlett Woods',
    'George Marshall', 'Grace Spencer', 'Oliver Harrison', 'Chloe Matthews',
    'Leo Davidson', 'Victoria Palmer', 'Arthur Stevens', 'Lily Robertson',
    'Edward Kennedy', 'Hannah Thompson', 'Harry Phillips', 'Zoe Campbell',
    'Charles Edwards', 'Lucy Walker'
];

// Injects the collaborative editing service into the Spreadsheet.
provide('spreadsheet', [CollaborativeEditingHandler]);

const spreadsheetRef = ref<InstanceType<typeof EjsSpreadsheet> | null>(null);
const shareButtonRef = ref<HTMLButtonElement | null>(null);
const currentUser: string =
    userNames[Math.floor(Math.random() * userNames.length)] ?? 'John Sullivan';

let adapter: SpreadsheetEditorAdapter | null = null;
let collaborationClient: CollaborationClient | null = null;
let shareButton: Button | null = null;
let copyButton: Button | null = null;
let shareTooltip: Tooltip | null = null;
let tooltipContent: HTMLElement | null = null;
let collaborationUrlInput: HTMLInputElement | null = null;
let copyButtonElement: HTMLButtonElement | null = null;
let copyResetTimer: number | null = null;
let initialized: boolean = false;

/** Returns the collaboration room name from the URL or creates a new room name. */
function getRoomName(): string {
    const currentUrl: URL = new URL(window.location.href);
    let roomName: string = (currentUrl.searchParams.get('id') || '').trim();

    if (!roomName) {
        roomName = Math.random().toString(32).slice(2);
        currentUrl.searchParams.set('id', roomName);
        window.history.replaceState(
            window.history.state,
            '',
            currentUrl.pathname + currentUrl.search + currentUrl.hash
        );
    }

    return roomName;
}

/** Resets the copy button text when the share tooltip is closed. */
function resetCopyButton(): void {
    if (copyButton) {
        copyButton.content = 'Copy URL';
        copyButton.dataBind();
    }
}

/** Closes the share tooltip and clears the copy-state timer. */
function closeShareTooltip(): void {
    shareTooltip?.close();
    resetCopyButton();

    if (copyResetTimer !== null) {
        window.clearTimeout(copyResetTimer);
        copyResetTimer = null;
    }
}

/** Opens the collaboration Share tooltip. */
function openShareTooltip(): void {
    if (!shareButtonRef.value || !shareTooltip) {
        return;
    }

    resetCopyButton();

    if (collaborationUrlInput) {
        collaborationUrlInput.value = window.location.href;
    }

    shareTooltip.open(shareButtonRef.value);
}

/** Copies the collaboration URL and displays the copied state temporarily. */
async function copyUrl(): Promise<void> {
    try {
        await navigator.clipboard.writeText(window.location.href);

        if (copyButton) {
            copyButton.content = 'Copied';
            copyButton.dataBind();
        }

        if (copyResetTimer !== null) {
            window.clearTimeout(copyResetTimer);
        }

        copyResetTimer = window.setTimeout(closeShareTooltip, 1500);
    } catch (error) {
        console.error('[Collaborative Editing] Failed to copy the URL.', error);
    }
}

/** Creates the content displayed in the Share tooltip. */
function createShareTooltipContent(): HTMLElement {
    const content: HTMLDivElement = document.createElement('div');
    const label: HTMLLabelElement = document.createElement('label');
    const row: HTMLDivElement = document.createElement('div');
    const input: HTMLInputElement = document.createElement('input');
    const buttonElement: HTMLButtonElement = document.createElement('button');

    content.className = 'share-tooltip-content';
    label.className = 'share-url-label';
    label.htmlFor = 'collaboration-url';
    label.textContent = 'Collaboration URL';
    row.className = 'share-url-row';
    input.id = 'collaboration-url';
    input.className = 'e-input share-url-input';
    input.type = 'text';
    input.value = window.location.href;
    input.readOnly = true;
    input.setAttribute('aria-label', 'Collaboration URL');
    collaborationUrlInput = input;
    buttonElement.type = 'button';

    row.append(input, buttonElement);
    content.append(label, row);

    copyButton = new Button({
        content: 'Copy URL',
        cssClass: 'e-primary copy-url-button'
    });
    copyButton.appendTo(buttonElement);
    buttonElement.addEventListener('click', copyUrl);
    copyButtonElement = buttonElement;

    return content;
}

/** Closes the Share tooltip when a pointer action occurs outside it. */
function closeTooltipOnOutsideClick(event: MouseEvent): void {
    const target: Node = event.target as Node;
    const tooltipElement: Element | null = document.querySelector(
        '.collaboration-share-tooltip'
    );

    if (shareButtonRef.value?.contains(target) || tooltipElement?.contains(target)) {
        return;
    }

    closeShareTooltip();
}

/** Closes the Share tooltip when the page is scrolled. */
function closeTooltipOnScroll(event: Event): void {
    const target: EventTarget | null = event.target;

    if (target instanceof Element && target.closest('.e-spreadsheet')) {
        return;
    }

    closeShareTooltip();
}

/** Loads the synchronized workbook and joins the collaboration room. */
async function onCreated(): Promise<void> {
    const spreadsheet: Spreadsheet | undefined =
        spreadsheetRef.value?.ej2Instances as Spreadsheet | undefined;

    if (!spreadsheet || initialized) {
        return;
    }

    initialized = true;
    const roomName: string = getRoomName();
    const spreadsheetAdapter = new SpreadsheetEditorAdapter(
        spreadsheet,
        serviceUrl,
        currentUser
    );

    try {
        await spreadsheetAdapter.loadFromServer('Sample', roomName);

        const client = new CollaborationClient(spreadsheetAdapter, {
            serviceUrl,
            connectionType: 'signalr',
            currentUser
        });

        adapter = spreadsheetAdapter;
        collaborationClient = client;
        await client.joinRoomAsync(roomName);
        console.log('[Collaborative Editing] Joined room', roomName);
    } catch (error) {
        initialized = false;
        console.error('[Collaborative Editing] Failed to join the room.', error);
    }
}

/** Sends a completed local Spreadsheet action to the Collaboration Server. */
function onActionComplete(args: unknown): void {
    adapter?.sendActionToServer(args);
}

onMounted(() => {
    if (!shareButtonRef.value) {
        return;
    }

    shareButton = new Button({
        content: 'Share',
        cssClass: 'e-primary share-button'
    });
    shareButton.appendTo(shareButtonRef.value);

    tooltipContent = createShareTooltipContent();
    shareTooltip = new Tooltip({
        content: tooltipContent,
        opensOn: 'Custom',
        position: 'BottomRight',
        cssClass: 'collaboration-share-tooltip'
    });
    shareTooltip.appendTo(shareButtonRef.value);

    shareButtonRef.value.addEventListener('click', openShareTooltip);
    document.addEventListener('mousedown', closeTooltipOnOutsideClick);
    window.addEventListener('scroll', closeTooltipOnScroll, true);
});

onBeforeUnmount(() => {
    shareButtonRef.value?.removeEventListener('click', openShareTooltip);
    document.removeEventListener('mousedown', closeTooltipOnOutsideClick);
    window.removeEventListener('scroll', closeTooltipOnScroll, true);
    copyButtonElement?.removeEventListener('click', copyUrl);

    if (copyResetTimer !== null) {
        window.clearTimeout(copyResetTimer);
    }

    shareTooltip?.destroy();
    shareButton?.destroy();
    copyButton?.destroy();
    tooltipContent = null;
    collaborationUrlInput = null;
    copyButtonElement = null;
    collaborationClient = null;
    adapter = null;
    initialized = false;
});
</script>

<template>
    <div class="collaborative-sample">
        <div class="collaboration-info-bar">
            <div class="collaboration-info-text">
                Copy and share this demo URL with others to collaborate in real time.
                The link contains a unique session ID that connects all participants
                to the same workbook.
            </div>
            <div class="share-tooltip-host">
                <button
                    id="share-collaboration-url"
                    ref="shareButtonRef"
                    type="button"
                ></button>
            </div>
        </div>
        <div class="spreadsheet-container">
            <!-- Enables real-time collaborative editing in the Spreadsheet. -->
            <ejs-spreadsheet
                ref="spreadsheetRef"
                width="100%"
                height="550px"
                :enableCollaborativeEditing="true"
                :created="onCreated"
                :actionComplete="onActionComplete"
            />
        </div>
    </div>
</template>
