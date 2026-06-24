import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import pandas as pd
from datetime import datetime
from services.database_service import get_trade_txns, update_trade_txn, insert_trade_txn

def trade_txn_editor_start(server=None):
    app = dash.Dash(
        __name__, 
        server=server if server is not None else True, 
        url_base_pathname='/trade_txn_editor/',
        external_stylesheets=[dbc.themes.FLATLY]
    )

    app.index_string = '''
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>Trade Transaction Editor</title>
            {%favicon%}
            {%css%}
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
                <script type="text/javascript">
                    // 1. Single click on a cell activates edit mode instantly
                    document.addEventListener('click', function(e) {
                        const cellValue = e.target.closest('.dash-spreadsheet .dash-cell-value');
                        if (cellValue) {
                            const cell = cellValue.closest('td');
                            if (cell && cell.getAttribute('data-dash-column') !== 'txn_id') {
                                if (!cell.querySelector('input') && !cell.querySelector('textarea')) {
                                    const dblClickEvent = new MouseEvent('dblclick', {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window
                                    });
                                    cellValue.dispatchEvent(dblClickEvent);
                                }
                            }
                        }
                    });

                    // 2. Pressing Enter when cell is focused switches it to edit mode
                    document.addEventListener('keydown', function(e) {
                        if (e.key === 'Enter') {
                            const activeCell = document.querySelector('.dash-spreadsheet td.cell--selected') || 
                                               document.querySelector('.dash-spreadsheet td.focused');
                            if (activeCell && activeCell.getAttribute('data-dash-column') !== 'txn_id') {
                                const hasInput = activeCell.querySelector('input') || activeCell.querySelector('textarea');
                                if (!hasInput) {
                                    // Not in edit mode: enter edit mode
                                    e.preventDefault();
                                    e.stopPropagation();
                                    const cellValue = activeCell.querySelector('.dash-cell-value');
                                    if (cellValue) {
                                        const dblClickEvent = new MouseEvent('dblclick', {
                                            bubbles: true,
                                            cancelable: true,
                                            view: window
                                        });
                                        cellValue.dispatchEvent(dblClickEvent);
                                    }
                                }
                            }
                        }
                    }, true); // Capture phase to intercept key event before Dash consumes it
                </script>
            </footer>
        </body>
    </html>
    '''

    def serve_layout():
        df = get_trade_txns()
        if df.empty:
            df = pd.DataFrame(columns=['txn_id', 'ticker', 'side', 'quantity', 'price', 'exec_time_utc'])

        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H1("Trade Transaction Editor", className="text-primary mt-4"),
                    html.P("Manage active portfolio trades and historical records.", className="text-muted mb-4 lead"),
                ], width=12)
            ]),

            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Database Management Console", className="font-weight-bold bg-white"),
                        dbc.CardBody([
                            html.Div(id='save-feedback-msg', className="text-center mb-3"),
                            dash_table.DataTable(
                                id='trade-txn-table',
                                columns=[{"name": i, "id": i, "editable": (i != 'txn_id')} for i in df.columns],
                                data=df.to_dict('records'),
                                editable=True,
                                row_selectable='single',
                                selected_rows=[],
                                sort_action="native",
                                filter_action="native",
                                page_action="native",
                                page_current=0,
                                page_size=20,
                                style_table={'overflowX': 'auto'},
                                style_cell={
                                    'backgroundColor': 'white',
                                    'color': '#333',
                                    'textAlign': 'left',
                                    'padding': '12px',
                                    'border': '1px solid #dee2e6'
                                },
                                style_header={
                                    'backgroundColor': '#f8f9fa',
                                    'fontWeight': 'bold',
                                    'color': '#2c3e50',
                                    'border': '1px solid #dee2e6'
                                },
                                style_data_conditional=[
                                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'},
                                    {'if': {'filter_query': '{txn_id} is blank'}, 'backgroundColor': '#fff3cd'}
                                ]
                            )
                        ])
                    ], className="shadow-sm border-0")
                ], width=12)
            ], className="mb-4"),

            dbc.Row([
                dbc.Col([
                    dbc.ButtonGroup([
                        dbc.Button('Buy Selected', id='buy-selected-button', color="warning", className="px-4"),
                        dbc.Button('New Buy', id='new-buy-button', color="primary", className="px-4"),
                        dbc.Button('Sell Selected', id='sell-button', color="danger", className="px-4"),
                        dbc.Button('Save Changes', id='save-button', color="success", className="px-4"),
                        dbc.Button('Refresh Data', id='refresh-button', color="info", className="px-4"),
                    ], className="shadow-sm")
                ], width={"size": 10, "offset": 1}, className="text-center")
            ])
        ], fluid=True, className="p-4 bg-white min-vh-100")

    app.layout = serve_layout

    @app.callback(
        [Output('trade-txn-table', 'data'),
         Output('save-feedback-msg', 'children'),
         Output('save-feedback-msg', 'style'),
         Output('trade-txn-table', 'selected_rows')],
        [Input('buy-selected-button', 'n_clicks'),
         Input('new-buy-button', 'n_clicks'),
         Input('sell-button', 'n_clicks'),
         Input('save-button', 'n_clicks'),
         Input('refresh-button', 'n_clicks')],
        [State('trade-txn-table', 'data'),
         State('trade-txn-table', 'selected_rows'),
         State('trade-txn-table', 'data_previous')],
        prevent_initial_call=True
    )
    def handle_table_actions(buy_sel_clicks, new_buy_clicks, sell_clicks, save_clicks, refresh_clicks, current_data, selected_rows, previous_data):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if button_id == 'refresh-button':
            new_df = get_trade_txns()
            return new_df.to_dict('records'), "Data successfully re-synced.", {'color': '#17a2b8'}, []

        if button_id == 'buy-selected-button':
            if not selected_rows:
                return dash.no_update, "Please select a record from the table.", {'color': '#dc3545'}, dash.no_update
            
            selected_index = selected_rows[0]
            row_to_copy = current_data[selected_index].copy()
            new_row = row_to_copy.copy()
            new_row['txn_id'] = None
            new_row['side'] = 'BUY'
            new_row['gross_amount'] = None
            new_row['exec_time_utc'] = datetime.now().astimezone().isoformat(timespec='seconds')
            
            updated_data = [new_row] + current_data
            return updated_data, "Draft BUY record created from selected. Please review and save.", {'color': '#fd7e14'}, []

        if button_id == 'new-buy-button':
            cols = list(current_data[0].keys()) if current_data else [
                'txn_id', 'ticker', 'market', 'side', 'exec_time_utc', 'currency', 'broker',
                'portfolio', 'quantity', 'price', 'gross_amount', 'fee', 'tax',
                'other_cost', 'broker_txn_id', 'note'
            ]
            
            new_row = {col: "" for col in cols}
            new_row['txn_id'] = None
            new_row['side'] = 'BUY'
            new_row['exec_time_utc'] = datetime.now().astimezone().isoformat(timespec='seconds')
            new_row['quantity'] = None
            new_row['price'] = None
            new_row['gross_amount'] = None
            new_row['fee'] = 0
            new_row['tax'] = 0
            new_row['other_cost'] = 0
            
            updated_data = [new_row] + current_data
            return updated_data, "Draft BUY record created. Please edit fields and save.", {'color': '#fd7e14'}, []

        if button_id == 'sell-button':
            if not selected_rows:
                return dash.no_update, "Please select a record from the table.", {'color': '#dc3545'}, dash.no_update
            
            selected_index = selected_rows[0]
            row_to_copy = current_data[selected_index].copy()
            new_row = row_to_copy.copy()
            new_row['txn_id'] = None
            new_row['side'] = 'SELL'
            new_row['gross_amount'] = None
            new_row['exec_time_utc'] = datetime.now().astimezone().isoformat(timespec='seconds')
            
            updated_data = [new_row] + current_data
            return updated_data, "Draft SELL record created. Please review and save.", {'color': '#fd7e14'}, []

        if button_id == 'save-button':
            changes_made = 0
            inserts_made = 0
            errors = 0
            
            for row in current_data:
                txn_id = row.get('txn_id')
                if txn_id is None or txn_id == "":
                    success = insert_trade_txn(row)
                    if success: inserts_made += 1
                    else: errors += 1
                else:
                    if previous_data:
                        prev_row = next((r for r in previous_data if r.get('txn_id') == txn_id), None)
                        if prev_row and row != prev_row:
                            success = update_trade_txn(txn_id, row)
                            if success: changes_made += 1
                            else: errors += 1

            msg = f"Database sync: +{inserts_made} created | {changes_made} updated | {errors} errors"
            color = '#28a745' if errors == 0 else '#dc3545'
            
            new_df = get_trade_txns()
            return new_df.to_dict('records'), msg, {'color': color, 'fontWeight': 'bold'}, []

        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    if not server:
        app.run(debug=True, use_reloader=False)
    return app

if __name__ == "__main__":
    trade_txn_editor_start()
