Here's a detailed Frontend Technical Specification for recreating the designs using pure HTML and vanilla CSS, based on the provided images.

---

## Frontend Technical Specification

### 1. General Design Language (from Image 1)

This image sets the overall background tone and general aesthetic direction for a larger application, indicating a soft, light, and airy feel.

*   **Overall Page Background / Section Tones:**
    *   **Top Section Color (Light Sky Blue):** `HEX: #B9D8F1`
        *   *Recommendation:* Use this as a dominant background color for header areas or upper halves of layout sections.
    *   **Bottom Section Color (Creamy Off-White):** `HEX: #F8F4EC`
        *   *Recommendation:* Use this for main content areas, body background, or as a base for cards and panels.
    *   **Gradient:** The transition between these two colors appears to be a soft, linear gradient from top to bottom.
        *   *Recommendation:* Implement as `linear-gradient(to bottom, #B9D8F1, #F8F4EC)` for the `body` or a large container element if a unified background is desired.

### 2. Paw Dom Analysis UI (from Image 2)

This image showcases the core brand guide and UI elements for the "Paw Dom" application.

#### 2.1. Color Palette (Brand Specific)

The image explicitly provides a color palette, which will be central to the UI.

*   **Primary Red (Accent/Call to Action):** `HEX: #ED6058`
    *   *CSS Variable:* `--pawdom-red`
*   **Light Pink (Secondary Background/Highlight):** `HEX: #F6EFEF`
    *   *CSS Variable:* `--pawdom-light-pink`
*   **Light Beige (Tertiary Background/Card Base):** `HEX: #F8F4EC`
    *   *CSS Variable:* `--pawdom-light-beige`
*   **Pure White (Text/Icon on Dark Backgrounds):** `HEX: #FFFEFE`
    *   *CSS Variable:* `--pawdom-white`
*   **Dark Text Color:** `HEX: #333333` (Estimated from 'FLONA.BTB' text)
    *   *CSS Variable:* `--pawdom-dark-text`

#### 2.2. Layout Structure

The layout features a prominent background element on the left and a grid-based content area on the right.

*   **Main Container:**
    *   *HTML Structure:* A main `div` container for the entire brand guide.
    *   *CSS Recommendation:* Use `display: grid` with two main columns or `position: relative` on the container with an `absolute` positioned background.
        ```css
        .brand-guide-container {
            display: grid;
            grid-template-columns: minmax(200px, 0.4fr) 1fr; /* Cat background column, content column */
            min-height: 100vh; /* Or specific height */
            gap: 0; /* Background is part of column 1 */
            background-color: var(--pawdom-light-beige); /* Fallback */
            overflow: hidden; /* To handle cat image */
        }
        /* Alternative for cat background */
        .brand-guide-container {
            position: relative;
            background-color: var(--pawdom-light-beige);
            padding-left: 25vw; /* Adjust based on cat image width */
            min-height: 100vh;
        }
        .cat-background {
            position: absolute;
            top: 0;
            left: 0;
            width: 25vw; /* Or fixed width */
            height: 100%;
            background-image: url('path/to/black_white_cat_fur.jpg');
            background-size: cover;
            background-position: center;
        }
        ```
*   **Content Area (Right Side):**
    *   *HTML Structure:* A `div` for all the UI cards and elements.
    *   *CSS Recommendation:* Use `display: grid` for flexible card arrangement.
        ```css
        .content-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); /* Adjust minmax based on desired card density */
            gap: 24px; /* Spacing between cards */
            padding: 40px; /* Overall padding around the content */
            align-items: start; /* Align items to the top of their grid cells */
        }
        /* Specific elements like the large red P could span multiple columns */
        .card.span-2-columns {
            grid-column: span 2;
        }
        ```

#### 2.3. Panel/Card Styling

All UI panels (cards) share a consistent aesthetic.

*   **Shape:** Rounded rectangles.
*   **Border Radius:** `20px` (consistent for all main cards, images, and larger interactive elements).
*   **Backgrounds:** Solid colors from the brand palette (`--pawdom-red`, `--pawdom-light-pink`, `--pawdom-light-beige`).
*   **Padding:**
    *   Internal padding within cards: `24px` to `32px` on all sides, depending on content density.
*   **Shadows:** No visible `box-shadow` or `text-shadow`. The design is flat and clean.

#### 2.4. Typography

A mix of custom and standard sans-serif fonts is used.

*   **Brand Identifier (FLONA.BTB):**
    *   `font-family: 'Inter', 'Helvetica Neue', sans-serif;` (or similar clean sans-serif)
    *   `font-size: 16px;`
    *   `font-weight: 400;`
    *   `text-transform: uppercase;`
    *   `color: var(--pawdom-dark-text);`
*   **Logo Text ("paw dom"):**
    *   *Recommendation:* This is a custom, rounded, playful font. If not provided as a web font, an SVG is ideal. If a font is required, consider Google Fonts like 'Fredoka One' or 'Varela Round' as a stylistic alternative.
    *   `font-family: 'CustomPawDomFont', 'Fredoka One', cursive;`
    *   `font-size: 48px;` (for main logo)
    *   `font-weight: bold;`
    *   `color: var(--pawdom-white);`
*   **Slogan ("where cats feel at home"):**
    *   `font-family: 'Inter', 'Helvetica Neue', sans-serif;`
    *   `font-size: 16px;`
    *   `font-weight: 400;`
    *   `color: var(--pawdom-white);`
*   **Font Samples (Amo Cho Pop Moru, Yomogi Font):**
    *   These are specific display fonts that would need to be embedded as web fonts (e.g., via `@font-face` or Google Fonts).
    *   **Main Sample Text:** `font-size: 24px; font-weight: bold;`
    *   **Alphabet/Numeric Listing:** `font-size: 16px; font-weight: normal;`
    *   **General Body Text:** `font-family: 'Inter', 'Helvetica Neue', sans-serif; font-size: 16px; color: var(--pawdom-dark-text);`

#### 2.5. Icons & Visual Cues

*   **Cat Head Icons:** Stylized, uses `--pawdom-white` on `--pawdom-red` background. Simple SVG paths or icon fonts.
*   **Paw Prints:** Used as a pattern in one card, and as an interactive icon.
    *   **Pattern:** Small, repeating SVG or background image.
    *   **Interactive Icon:** Uses `--pawdom-red` for the background, white for the paw print and arrow.
        *   `width: 60px; height: 60px;` (approx.)
        *   `border-radius: 50%;` (circular)
        *   `display: flex; justify-content: center; align-items: center;` (for centering the icon)
*   **Cat Images:** Embedded directly into cards.
    *   `border-radius: 20px;` (to match card styling).
    *   `width: 100%; height: auto; display: block;` (to fill container without distortion).

#### 2.6. Interaction Elements

*   The circular paw print with an arrow at the bottom suggests a "Next" or "Navigate" button.
    *   *Recommendation:* Implement as a `<button>` or `<a>` tag with the styling mentioned above. Add a subtle `:hover` state (e.g., slight scale or box-shadow) for interactivity.

### 3. Login Page (from Image 3)

This design features a central modal overlaid on a dynamic image background, characteristic of Pinterest's login.

#### 3.1. Overall Layout

*   **Background:** The entire viewport should be covered by a dynamic, image-rich background (mimicking a Pinterest board).
    *   *HTML Structure:* `<body style="background-image: url('path/to/pinterest-background-grid.jpg'); background-size: cover; background-position: center; background-attachment: fixed;">`
    *   *CSS Recommendation:* `body { background-image: url('path/to/pinterest-background-grid.jpg'); background-size: cover; background-position: center; background-attachment: fixed; min-height: 100vh; display: flex; justify-content: center; align-items: center; }`
*   **Login Modal:** Centered horizontally and vertically on the screen.
    *   *HTML Structure:* `<div class="login-modal-container"> ... </div>`
    *   *CSS Recommendation:* `position: relative; width: 100%; height: 100%; display: flex; justify-content: center; align-items: center;` for a wrapper, then for the modal itself:
        ```css
        .login-modal {
            background-color: rgba(255, 255, 255, 0.95); /* Slightly transparent white */
            border-radius: 8px;
            padding: 40px;
            width: 100%;
            max-width: 400px; /* Fixed width for the modal */
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); /* Subtle shadow */
            text-align: center; /* For centered content */
        }
        ```

#### 3.2. Color Palette (Login Specific)

*   **Pinterest Red (Primary Accent):** `HEX: #E60023`
    *   *CSS Variable:* `--pinterest-red`
*   **Dark Text:** `HEX: #333333`
    *   *CSS Variable:* `--login-dark-text`
*   **Light Gray Text/Placeholder:** `HEX: #767676`
    *   *CSS Variable:* `--login-light-gray-text`
*   **Input Border Gray:** `HEX: #E0E0E0`
    *   *CSS Variable:* `--login-input-border`
*   **Pure White:** `HEX: #FFFFFF`
    *   *CSS Variable:* `--login-white`

#### 3.3. Input Fields

*   **Borders:** `1px solid var(--login-input-border);`
*   **Border Radius:** `6px;`
*   **Padding:** `12px 16px;`
*   **Background:** `var(--login-white);`
*   **Width:** `100%;` (to fill parent container)
*   **Margin:** `margin-bottom: 16px;` (between fields)
*   **Typography:**
    *   `font-family: 'Helvetica Neue', Arial, sans-serif;`
    *   `font-size: 16px;`
    *   `color: var(--login-dark-text);`
    *   `::placeholder { color: var(--login-light-gray-text); }`

#### 3.4. Buttons

*   **Primary Login Button:**
    *   `background-color: var(--pinterest-red);`
    *   `color: var(--login-white);`
    *   `border: none;`
    *   `border-radius: 6px;`
    *   `padding: 12px 16px;`
    *   `width: 100%;`
    *   `font-family: 'Helvetica Neue', Arial, sans-serif;`
    *   `font-size: 16px;`
    *   `font-weight: bold;`
    *   `cursor: pointer;`
    *   `margin-top: 10px;` (after inputs)
    *   *Hover Effect:* `background-color: darken(var(--pinterest-red), 10%);` (or a slightly darker red)
*   **"Forgot your password?" Link:**
    *   `color: var(--login-dark-text);`
    *   `font-family: 'Helvetica Neue', Arial, sans-serif;`
    *   `font-size: 14px;`
    *   `text-decoration: none;`
    *   `display: block;` (to ensure it takes full width and breaks line)
    *   `margin-top: 20px;`
    *   *Hover Effect:* `text-decoration: underline;`

#### 3.5. Typography (Login Specific)

*   **Pinterest Logo:**
    *   *Recommendation:* Use the official Pinterest SVG logo for best fidelity. If text is needed:
        *   `font-family: 'Helvetica Neue', Arial, sans-serif;` (or similar clean sans-serif)
        *   `font-size: 32px;`
        *   `font-weight: bold;`
        *   `color: var(--pinterest-red);`
        *   `margin-bottom: 20px;`
*   **Login Prompt Text ("Welcome to Pinterest"):**
    *   `font-family: 'Helvetica Neue', Arial, sans-serif;`
    *   `font-size: 24px;`
    *   `font-weight: bold;`
    *   `color: var(--login-dark-text);`
    *   `margin-bottom: 24px;`
*   **Small separator text ("OR"):**
    *   `font-family: 'Helvetica Neue', Arial, sans-serif;`
    *   `font-size: 12px;`
    *   `color: var(--login-light-gray-text);`
    *   `text-transform: uppercase;`
    *   `margin: 20px 0;`

#### 3.6. Visual Effects

*   **Background Blur:** The background images behind the modal appear slightly blurred, enhancing the modal's focus.
    *   *Recommendation:* This effect is typically achieved on the background *element itself*, not the modal. For a dynamic background, it's complex, but if the background image is static, you could apply `filter: blur(5px);` to the `body` and then place the modal on top. A simpler approach if the background is dynamic is to keep the modal slightly opaque as suggested with `rgba()`.
*   **Modal Shadow:** Already covered in `login-modal` styling.

---