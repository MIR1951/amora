/// Top and bottom bars (port of GlassTopBar / BottomDock from android ui/components/Components.kt).
/// Place them OVER the scrolling content so it scrolls (blurred) underneath:
///
///     ScrollView { ... }
///         .safeAreaInset(edge: .top, spacing: 0) {
///             GlassTopBar(title: "Savat", onBack: { router.back() })
///         }
///         .safeAreaInset(edge: .bottom, spacing: 0) {
///             BottomDock { BigButton(text: "Buyurtma berish", onClick: { ... }) }
///         }
///
/// Surface:
/// - `GlassTopBar(title: String, onBack: (() -> Void)?)`
///   `GlassTopBar(title:onBack:actions: { ... })`, `GlassTopBar(title:onBack:below: { ... })`,
///   `GlassTopBar(title:onBack:actions: { ... }, below: { ... })`
///   (label `actions:` / `below:` explicitly; a bare trailing closure is ambiguous)
/// - `BottomDock(@ViewBuilder content:)`  - content stacked vertically (VStack spacing 0), 16 side padding

import SwiftUI

/// Yuqori satr: orqaga tugmasi va sarlavha. Kontent uning ostiga xiralashib kirib ketadi.
/// `onBack` berilmasa, tugma chizilmaydi. `actions`: o'ngdagi tugmalar. `below`: sarlavha ostidagi qo'shimcha qator.
struct GlassTopBar<Actions: View, Below: View>: View {
    let title: String
    let onBack: (() -> Void)?
    private let actions: Actions
    private let below: Below
    @Environment(\.amoraColors) private var colors

    init(
        title: String,
        onBack: (() -> Void)?,
        @ViewBuilder actions: () -> Actions,
        @ViewBuilder below: () -> Below
    ) {
        self.title = title
        self.onBack = onBack
        self.actions = actions()
        self.below = below()
    }

    private var hasBelow: Bool {
        Below.self != EmptyView.self
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 0) {
                if let onBack {
                    RoundButton(icon: .back, label: "Orqaga", onClick: onBack)
                    Spacer().frame(width: 12)
                }
                Text(title)
                    .amoraText(.headlineSmall)
                    .foregroundColor(colors.onBackground)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityAddTraits(.isHeader)
                actions
            }
            .padding(.horizontal, 16)
            if hasBelow {
                Spacer().frame(height: 12)
                below
            }
        }
        .padding(.top, 8)
        .padding(.bottom, 16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(GlassStrip(fade: .bottom).ignoresSafeArea(edges: .top))
    }
}

extension GlassTopBar where Actions == EmptyView, Below == EmptyView {
    init(title: String, onBack: (() -> Void)?) {
        self.init(title: title, onBack: onBack, actions: { EmptyView() }, below: { EmptyView() })
    }
}

extension GlassTopBar where Below == EmptyView {
    init(title: String, onBack: (() -> Void)?, @ViewBuilder actions: () -> Actions) {
        self.init(title: title, onBack: onBack, actions: actions, below: { EmptyView() })
    }
}

extension GlassTopBar where Actions == EmptyView {
    init(title: String, onBack: (() -> Void)?, @ViewBuilder below: () -> Below) {
        self.init(title: title, onBack: onBack, actions: { EmptyView() }, below: below)
    }
}

/// Ekran pastida suzib turadigan asosiy tugma joyi: ortidagi kontent xiralashib ko'rinadi.
/// Uy tugmasi chizig'i bor iPhone'larda pastki chekinish shu chiziq hisobiga kichikroq.
struct BottomDock<Content: View>: View {
    private let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        let homeIndicator = AmoraWindow.bottomInset
        VStack(alignment: .leading, spacing: 0) {
            content
        }
        .padding(.horizontal, 16)
        .padding(.top, 26)
        .padding(.bottom, homeIndicator > 0 ? 4 : 14)
        .frame(maxWidth: .infinity)
        .background(GlassStrip(fade: .top).ignoresSafeArea(edges: .bottom))
    }
}
